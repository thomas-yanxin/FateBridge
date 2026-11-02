/* Translation of Francou & Simon's VSOP2013.f (GF-JLS-2013,
 * GF-JLS-1212). EMB only, full series, positions only; immutable coefficients embedded at build time. The coefficients,
 * secular-term handling, elliptic conversion and ICRS rotation are from
 * the original IMCCE release. No reference ephemeris is read here. */
#include <complex.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

typedef struct { uint32_t variable, power; double a, b, s, c; } Term;
static Term *terms = NULL;
static uint32_t count = 0;

extern const unsigned char fatebridge_vsop_series[];
extern const unsigned char fatebridge_vsop_series_end[];
int vsop2013_ready(void) { return terms != NULL; }
int vsop2013_init_embedded(void) {
    if (terms != NULL) return 0;
    const size_t size = (size_t)((uintptr_t)fatebridge_vsop_series_end - (uintptr_t)fatebridge_vsop_series);
    if (sizeof(Term) != 40 || size < 4) return 1;
    uint32_t n;
    memcpy(&n, fatebridge_vsop_series, 4);
    if (n != 294425 || size != 4 + (size_t)n * sizeof(Term)) return 2;
    Term *loaded = malloc(sizeof(Term) * n);
    if (!loaded) return 3;
    memcpy(loaded, fatebridge_vsop_series + 4, sizeof(Term) * n);
    for (uint32_t i = 0; i < n; i++) {
        Term v = loaded[i];
        if (v.variable > 5 || v.power > 20 || !isfinite(v.a) || !isfinite(v.b) || !isfinite(v.s) || !isfinite(v.c)) {
            free(loaded); return 4;
        }
    }
    count = n; terms = loaded;
    return 0;
}

int vsop2013_emb(double jd_tdb, double *out) {
    if (!terms || !isfinite(jd_tdb)) return 1;
    double powers[21];
    powers[0] = 1.; powers[1] = (jd_tdb - 2451545.) / 365250.;
    for (int n = 2; n <= 20; n++) powers[n] = powers[1] * powers[n-1];
    for (int n = 0; n < 6; n++) out[n] = 0.;
    for (uint32_t n = 0; n < count; n++) {
        Term t = terms[n];
        double arg = t.a + t.b * powers[1];
        out[t.variable] += powers[t.power] * (t.s * sin(arg) + t.c * cos(arg));
    }
    const double dpi = 6.283185307179586;
    out[1] = fmod(out[1] + 6283.075850353215 * powers[1], dpi);
    if (out[1] < 0.) out[1] += dpi;
    const double xa=out[0], xl=out[1], xk=out[2], xh=out[3], xq=out[4], xp=out[5];
    const double xfi=sqrt(1.-xk*xk-xh*xh), xki=sqrt(1.-xq*xq-xp*xp), u=1./(1.+xfi);
    double complex z = xk + I*xh, z1=conj(z), z3=0., zteta=0.;
    const double ex=cabs(z), ex2=ex*ex, ex3=ex2*ex, gl=fmod(xl,dpi), gm=gl-atan2(xh,xk);
    double e=gl+(ex-.125*ex3)*sin(gm)+.5*ex2*sin(2.*gm)+.375*ex3*sin(3.*gm), rsa=0.;
    int converged=0;
    for (int n=0; n<50; n++) {
        zteta=cexp(I*e); z3=z1*zteta;
        double dl=gl-e+cimag(z3);
        rsa=1.-creal(z3); e+=dl/rsa;
        if (fabs(dl)<1.e-15) { converged=1; break; }
    }
    if (!converged) return 2;
    z1=u*z*cimag(z3);
    double complex z2=cimag(z1)-I*creal(z1), zto=(-z+zteta+z2)/rsa;
    double xcw=creal(zto), xsw=cimag(zto), xm=xp*xcw-xq*xsw, xr=xa*rsa;
    out[6]=xr*(xcw-2.*xp*xm); out[7]=xr*(xsw+2.*xq*xm); out[8]=-2.*xr*xki*xm;
    const double pi=3.141592653589793;
    double eps=(23.+26./60.+21.41136/3600.)*pi/180.;
    double phi=-.05188*pi/180./3600., ce=cos(eps), se=sin(eps), cp=cos(phi), sp=sin(phi);
    out[9]=cp*out[6]-sp*ce*out[7]+sp*se*out[8];
    out[10]=sp*out[6]+cp*ce*out[7]-cp*se*out[8];
    out[11]=se*out[7]+ce*out[8];
    for (int n=0; n<12; n++) if (!isfinite(out[n])) return 3;
    return 0;
}
