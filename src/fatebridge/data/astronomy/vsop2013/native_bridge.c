/* VSOP2013 EMB, original AU/ICRS conversion, full built-in ERFA dtdb. */
#include <math.h>
#include <stddef.h>
#include "erfa.h"
extern int vsop2013_emb(double, double *);
extern double swi_epsiln(double, int);
int fatebridge_vsop2013_native_emb(double tt, double *out) {
    double p[12], y, z, epsilon;
    if (out == NULL) return -1;
    for (int i=0; i<3; i++) out[i] = NAN;
    for (int i=0; i<12; i++) p[i] = NAN;
    if (!isfinite(tt)) return -1;
    double correction = eraDtdb(2451545., tt - 2451545., 0., 0., 0., 0.);
    if (!isfinite(correction) || fabs(correction) > .01) return -1;
    int code = vsop2013_emb(tt + correction / 86400., p);
    if (code != 0) return -1;
    for (int i=0; i<12; i++) if (!isfinite(p[i])) return -1;
    double factor = 149597870.691 / 149597870.7;
    double x = p[9]*factor, a = p[10]*factor, b = p[11]*factor;
    epsilon = swi_epsiln(2451545., 0);
    y = cos(epsilon)*a + sin(epsilon)*b;
    z = -sin(epsilon)*a + cos(epsilon)*b;
    out[0] = atan2(y,x);
    out[1] = atan2(z,hypot(x,y));
    out[2] = sqrt(x*x+y*y+z*z);
    if (!isfinite(out[0]) || !isfinite(out[1]) || !isfinite(out[2]) || out[2] <= 0.) {
        for (int i=0; i<3; i++) out[i] = NAN;
        return -1;
    }
    return 0;
}
