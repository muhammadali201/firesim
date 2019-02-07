#ifndef RTLSIM
#include "simif_f1.h"
#else
#include "simif_emul.h"
#endif
#include "firesim_top.h"
#include "fesvr/firesim_fesvr.h"

#if defined(SIMULATION_XSIM) || defined(RTLSIM)
// use a small step size for rtl sim
#define DESIRED_STEPSIZE (128)
#else
#define DESIRED_STEPSIZE (2004765L)
#endif
#ifdef RTLSIM

// top for RTL sim
class firesim_f1_t:
    public simif_emul_t, public firesim_top_t
{
    public:
        firesim_f1_t(int argc, char** argv, firesim_fesvr_t* fesvr):
            firesim_top_t(argc, argv, fesvr, DESIRED_STEPSIZE) { }
};
#else
// top for FPGA simulation on F1
class firesim_f1_t:
    public simif_f1_t, public firesim_top_t
{
    public:
        firesim_f1_t(int argc, char** argv, firesim_fesvr_t* fesvr):
            (argc, argv, fesvr, DESIRED_STEPSIZE), simif_f1_t(argc, argv) { }
};
#endif

int main(int argc, char** argv) {
    firesim_fesvr_t fesvr(std::vector<std::string>(argv + 1, argv + argc));
    printf("firesim_f1: main: done with fesvr, creating firesim_f1_t object with constructor calls \n");
    firesim_f1_t firesim(argc, argv, &fesvr);
    printf("Address of firesim (firesim_f1_t) object = %p,   \n",&firesim);
    printf("firesim_f1: main: calling firesim_top_t.init function,  \n");
    firesim.init(argc, argv);
    printf("firesim_f1: main: calling firesim_top_t.run function,  \n");
    firesim.run();
    return firesim.finish();
}
