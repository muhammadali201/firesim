#ifndef __TRACERV_H
#define __TRACERV_H

#include "endpoints/endpoint.h"
#include <vector>


class tracerv_t: public endpoint_t
{
    public:
        tracerv_t(simif_t *sim, std::vector<std::string> &args, int tracervno);
        ~tracerv_t();

        virtual void init();
        virtual void tick();
        virtual bool terminate() { return false; }
        virtual int exit_code() { return 0; }
	virtual bool done() { return read(TRACERVWIDGET_0(done)); }
    private:
       // TRACERVWIDGET_struct * mmio_addrs;
        simif_t* sim;
        FILE * tracefile;
        uint64_t start_cycle, end_cycle, cur_cycle;
};

#endif // __TRACERV_H
