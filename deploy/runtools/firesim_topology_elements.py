""" Node types necessary to construct a FireSimTopology. """

import logging

from runtools.switch_model_config import AbstractSwitchToSwitchConfig
from util.streamlogger import StreamLogger
from fabric.api import *

rootLogger = logging.getLogger()

class FireSimNode(object):
    """ This represents a node in the high-level FireSim Simulation Topology
    Graph. These nodes are either

    a) Actual Switches
    b) Dummy Switches
    c) Simulation Nodes

    Initially, a user just constructs a standard tree that describes the
    target. Then, they define a bunch of passes that run on the tree, for
    example:

        1) Mapping nodes to host EC2 instances
        2) Assigning MAC addresses to simulators
        3) Assigning workloads to run to simulators

    """

    def __init__(self):
        self.downlinks = []
        self.uplinks = []
        self.host_instance = None

    def add_downlink(self, firesimnode):
        """ A "downlink" is a link that will take you further from the root
        of the tree. Users define a tree topology by specifying "downlinks".
        Uplinks are automatically inferred. """
        firesimnode.add_uplink(self)
        self.downlinks.append(firesimnode)

    def add_downlinks(self, firesimnodes):
        """ Just a convenience function to add multiple downlinks at once.
        Assumes downlinks in the supplied list are ordered. """
        [self.add_downlink(node) for node in firesimnodes]

    def add_uplink(self, firesimnode):
        """ This is only for internal use - uplinks are automatically populated
        when a node is specified as the downlink of another.

        An "uplink" is a link that takes you towards one of the roots of the
        tree."""
        self.uplinks.append(firesimnode)

    def num_links(self):
        """ Return the total number of nodes. """
        return len(self.downlinks) + len(self.uplinks)

    def run_node_simulation(self):
        """ Override this to provide the ability to launch your simulation. """
        pass

    def terminate_node_simulation(self):
        """ Override this to provide the ability to terminate your simulation. """
        pass

    def assign_host_instance(self, host_instance_run_farm_object):
        self.host_instance = host_instance_run_farm_object

    def get_host_instance(self):
        return self.host_instance


class FireSimServerNode(FireSimNode):
    """ This is a simulated server instance in FireSim. """
    SERVERS_CREATED = 0

    def __init__(self, server_hardware_config=None, server_link_latency=None,
                 server_bw_max=None, server_profile_interval=None,
                 trace_enable=None, trace_start=None, trace_end=None):
        super(FireSimServerNode, self).__init__()
        self.server_hardware_config = server_hardware_config
        self.server_link_latency = server_link_latency
        self.server_bw_max = server_bw_max
        self.server_profile_interval = server_profile_interval
        self.trace_enable = trace_enable
        self.trace_start = trace_start
        self.trace_end = trace_end
        self.job = None
        self.server_id_internal = FireSimServerNode.SERVERS_CREATED
        FireSimServerNode.SERVERS_CREATED += 1

    def set_server_hardware_config(self, server_hardware_config):
        self.server_hardware_config = server_hardware_config

    def get_server_hardware_config(self):
        return self.server_hardware_config

    def assign_mac_address(self, macaddr):
        self.mac_address = macaddr

    def get_mac_address(self):
        return self.mac_address

    def diagramstr(self):
        msg = """{}:{}\n----------\nMAC: {}\n{}\n{}""".format("FireSimServerNode",
                                                   str(self.server_id_internal),
                                                   str(self.mac_address),
                                                   str(self.job),
                                                   str(self.server_hardware_config))
        return msg

    def get_sim_start_command(self, slotno):
        """ return the command to start the simulation. assumes it will be
        called in a directory where its required_files are already located.
        """
        return self.server_hardware_config.get_boot_simulation_command(
            self.get_mac_address(), self.get_rootfs_name(), slotno,
            self.server_link_latency, self.server_bw_max,
            self.server_profile_interval, self.get_bootbin_name(),
            self.trace_enable, self.trace_start, self.trace_end)

    def copy_back_job_results_from_run(self, slotno):
        """
        1) Make the local directory for this job's output
        2) Copy back UART log
        3) Mount rootfs on the remote node and copy back files

        TODO: move this somewhere else, it's kinda in a weird place...
        """
        jobinfo = self.get_job()
        simserverindex = slotno
        job_results_dir = self.get_job().parent_workload.job_results_dir
        job_dir = """{}/{}/""".format(job_results_dir, jobinfo.jobname)
        with StreamLogger('stdout'), StreamLogger('stderr'):
            localcap = local("""mkdir -p {}""".format(job_dir), capture=True)
            rootLogger.debug("[localhost] " + str(localcap))
            rootLogger.debug("[localhost] " + str(localcap.stderr))

        # mount rootfs, copy files from it back to local system
        mountpoint = """/home/centos/sim_slot_{}/mountpoint""".format(simserverindex)
        with StreamLogger('stdout'), StreamLogger('stderr'):
            run("""sudo mkdir -p {}""".format(mountpoint))
            run("""sudo mount /home/centos/sim_slot_{}/{} {}""".format(simserverindex, self.get_rootfs_name(), mountpoint))
            run("""sudo chmod -Rf 777 {}""".format(mountpoint))

        ## copy back files from inside the rootfs
        with warn_only(), StreamLogger('stdout'), StreamLogger('stderr'):
            for outputfile in jobinfo.outputs:
                get(remote_path=mountpoint + outputfile, local_path=job_dir)

        ## unmount
        with StreamLogger('stdout'), StreamLogger('stderr'):
            run("""sudo umount {}""".format(mountpoint))

        ## copy output files generated by the simulator that live on the host:
        ## e.g. uartlog, memory_stats.csv, etc
        remote_sim_run_dir = """/home/centos/sim_slot_{}/""".format(simserverindex)
        for simoutputfile in jobinfo.simoutputs:
            with StreamLogger('stdout'), StreamLogger('stderr'):
                get(remote_path=remote_sim_run_dir + simoutputfile, local_path=job_dir)

    def get_sim_kill_command(self, slotno):
        """ return the command to kill the simulation. assumes it will be
        called in a directory where its required_files are already located.
        """
        return self.server_hardware_config.get_kill_simulation_command()

    def get_required_files_local_paths(self):
        """ Return local paths of all stuff needed to run this simulation as
        an array. """
        all_paths = []
        # todo handle none case
        all_paths.append(self.get_job().rootfs_path())
        all_paths.append(self.get_job().bootbinary_path())

        all_paths.append(self.server_hardware_config.get_local_driver_path())
        all_paths.append(self.server_hardware_config.get_local_runtime_conf_path())
        return all_paths

    def get_agfi(self):
        """ Return the AGFI that should be flashed. """
        return self.server_hardware_config.agfi

    def assign_job(self, job):
        """ Assign a job to this node. """
        self.job = job

    def get_job(self):
        """ Get the job assigned to this node. """
        return self.job

    def get_job_name(self):
        return self.job.jobname

    def get_rootfs_name(self):
        return self.get_job().rootfs_path().split("/")[-1]

    def get_bootbin_name(self):
        return self.get_job().bootbinary_path().split("/")[-1]


class FireSimSwitchNode(FireSimNode):
    """ This is a simulated switch instance in FireSim.

    This is purposefully simple. Abstractly, switches don't do much/have
    much special configuration."""

    # used to give switches a global ID
    SWITCHES_CREATED = 0

    def __init__(self, switching_latency=None, link_latency=None):
        super(FireSimSwitchNode, self).__init__()
        self.switch_id_internal = FireSimSwitchNode.SWITCHES_CREATED
        FireSimSwitchNode.SWITCHES_CREATED += 1
        self.switch_table = None
        self.switch_link_latency = link_latency
        self.switch_switching_latency = switching_latency

        # switch_builder is a class designed to emit a particular switch model.
        # it should take self and then be able to emit a particular switch model's
        # binary. this is populated when build_switch_sim_binary is called
        #self.switch_builder = None
        self.switch_builder = AbstractSwitchToSwitchConfig(self)

    def build_switch_sim_binary(self):
        """ This actually emits a config and builds the switch binary that
        can be used to do the simulation. """
        self.switch_builder.buildswitch()

    def get_required_files_local_paths(self):
        """ Return local paths of all stuff needed to run this simulation as
        array. """
        all_paths = []
        all_paths.append(self.switch_builder.switch_binary_local_path())
        return all_paths

    def get_switch_start_command(self):
        return self.switch_builder.run_switch_simulation_command()

    def get_switch_kill_command(self):
        return self.switch_builder.kill_switch_simulation_command()

    def copy_back_switchlog_from_run(self, job_results_dir, switch_slot_no):
        """
        Copy back the switch log for this switch

        TODO: move this somewhere else, it's kinda in a weird place...
        """
        job_dir = """{}/switch{}/""".format(job_results_dir, self.switch_id_internal)

        with StreamLogger('stdout'), StreamLogger('stderr'):
            localcap = local("""mkdir -p {}""".format(job_dir), capture=True)
            rootLogger.debug("[localhost] " + str(localcap))
            rootLogger.debug("[localhost] " + str(localcap.stderr))

        ## copy output files generated by the simulator that live on the host:
        ## e.g. uartlog, memory_stats.csv, etc
        remote_sim_run_dir = """/home/centos/switch_slot_{}/""".format(switch_slot_no)
        for simoutputfile in ["switchlog"]:
            with StreamLogger('stdout'), StreamLogger('stderr'):
                get(remote_path=remote_sim_run_dir + simoutputfile, local_path=job_dir)


    def diagramstr(self):
        msg = """{}:{}\n---------\ndownlinks: {}\nswitchingtable: {}""".format(
            "FireSimSwitchNode", str(self.switch_id_internal), ", ".join(map(str, self.downlinkmacs)),
            ", ".join(map(str, self.switch_table)))
        return msg
