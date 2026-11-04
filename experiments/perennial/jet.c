/* Hot loops for Perennial. Compile with -O2 -ffp-contract=off for reproducible doubles. */
#include <complex.h>
int jet(double zr, double zi, double cr, double ci, long P, double *out) {
    double complex z = zr + I * zi, c = cr + I * ci;
    double complex a = 1, b = 0, d = 0, e = 0;
    for (long i = 0; i < P; i++) {
        d = 2 * (a * a + z * d);
        e = 2 * (b * a + z * e);
        b = 2 * z * b + 1;
        a = 2 * z * a;
        z = z * z + c;
        if (creal(z) * creal(z) + cimag(z) * cimag(z) > 1e12) return 0;
    }
    double complex v[5] = {z, a, b, d, e};
    for (int k = 0; k < 5; k++) { out[2 * k] = creal(v[k]); out[2 * k + 1] = cimag(v[k]); }
    return 1;
}
int orbit0(double cr, double ci, long P, double *out) {
    double complex c = cr + I * ci, z = 0, dz = 0;
    for (long i = 0; i < P; i++) {
        dz = 2 * z * dz + 1;
        z = z * z + c;
        if (creal(z) * creal(z) + cimag(z) * cimag(z) > 1e12) return 0;
    }
    out[0] = creal(z); out[1] = cimag(z); out[2] = creal(dz); out[3] = cimag(dz);
    return 1;
}
