/**
 * starship_core.c - High-performance freestanding C99 flight dynamics kernel.
 *
 * Implements the inner 3-DoF equations of motion, aerodynamic drag/lift,
 * and 4th-order Runge-Kutta numerical integration step for Starship flip guidance.
 * Designed for bare-metal flight computers and Oxide C99-emission compatibility.
 */

#include <math.h>
#include <stdint.h>
#include <stdbool.h>

#define G0 9.80665
#define PI 3.14159265358979323846

typedef struct {
    double x;               /* Downrange position [m] */
    double z;               /* Altitude [m] */
    double vx;              /* Horizontal velocity [m/s] */
    double vz;              /* Vertical velocity [m/s] */
    double theta;           /* Pitch angle [rad] */
    double omega;           /* Pitch rate [rad/s] */
    double propellant_mass; /* Remaining propellant mass [kg] */
} NativeFlightState;

typedef struct {
    double dry_mass;
    double max_thrust_per_engine;
    double isp_sea_level;
    double length;
    double diameter;
    double gimbal_moment_arm;
    double moment_of_inertia_pitch;
} NativeVehicleParams;

typedef struct {
    double throttle;
    double gimbal_rad;
    int32_t active_engines;
} NativeControlInput;

static inline double calc_air_density(double altitude_m) {
    if (altitude_m <= 0.0) return 1.225;
    return 1.225 * exp(-altitude_m / 8500.0);
}

void compute_derivatives_c(
    const NativeFlightState* s,
    const NativeVehicleParams* v,
    const NativeControlInput* u,
    double derivs[7]
) {
    double curr_mass = v->dry_mass + s->propellant_mass;
    double f_thrust = u->throttle * u->active_engines * v->max_thrust_per_engine;

    /* Aerodynamics */
    double speed = hypot(s->vx, s->vz);
    double rho = calc_air_density(s->z);
    double q_dyn = 0.5 * rho * speed * speed;

    double uv_x = (speed > 1e-4) ? (s->vx / speed) : 0.0;
    double uv_z = (speed > 1e-4) ? (s->vz / speed) : -1.0;

    double body_x = sin(s->theta);
    double body_z = cos(s->theta);
    double cos_beta = body_x * uv_x + body_z * uv_z;
    if (cos_beta > 1.0) cos_beta = 1.0;
    if (cos_beta < -1.0) cos_beta = -1.0;
    double beta = acos(cos_beta);
    double alpha = (beta <= (PI / 2.0)) ? beta : (PI - beta);

    double sin_a = sin(alpha);
    double cos_a = cos(alpha);
    double area_ax = PI * (v->diameter / 2.0) * (v->diameter / 2.0);
    double area_broad = v->length * v->diameter;
    double cd = 0.30 * (cos_a * cos_a) + 1.35 * (sin_a * sin_a);
    double ref_area = area_ax * (cos_a * cos_a) + area_broad * (sin_a * sin_a);
    double drag_force = q_dyn * cd * ref_area;

    double f_aero_x = -drag_force * uv_x;
    double f_aero_z = -drag_force * uv_z;

    /* Thrust vector */
    double thrust_angle = s->theta - u->gimbal_rad;
    double f_thrust_x = f_thrust * sin(thrust_angle);
    double f_thrust_z = f_thrust * cos(thrust_angle);

    /* Accelerations */
    double ax = (f_thrust_x + f_aero_x) / curr_mass;
    double az = (f_thrust_z + f_aero_z - curr_mass * G0) / curr_mass;

    /* Pitch torque */
    double moment_thrust = -f_thrust * sin(u->gimbal_rad) * v->gimbal_moment_arm;
    double moment_aero_damp = -0.15 * q_dyn * area_broad * v->length * s->omega;
    double alpha_ang = (moment_thrust + moment_aero_damp) / v->moment_of_inertia_pitch;

    /* Mass depletion */
    double m_dot = (f_thrust > 0.0 && s->propellant_mass > 0.0) ? -(f_thrust / (v->isp_sea_level * G0)) : 0.0;

    derivs[0] = s->vx;
    derivs[1] = s->vz;
    derivs[2] = ax;
    derivs[3] = az;
    derivs[4] = s->omega;
    derivs[5] = alpha_ang;
    derivs[6] = m_dot;
}

/**
 * Executes a single 4th-order Runge-Kutta numerical integration step in C.
 */
void native_step_rk4(
    NativeFlightState* s,
    const NativeVehicleParams* v,
    const NativeControlInput* u,
    double dt
) {
    double k1[7], k2[7], k3[7], k4[7];
    NativeFlightState tmp;

    compute_derivatives_c(s, v, u, k1);

    tmp.x = s->x + 0.5 * dt * k1[0];
    tmp.z = s->z + 0.5 * dt * k1[1];
    tmp.vx = s->vx + 0.5 * dt * k1[2];
    tmp.vz = s->vz + 0.5 * dt * k1[3];
    tmp.theta = s->theta + 0.5 * dt * k1[4];
    tmp.omega = s->omega + 0.5 * dt * k1[5];
    tmp.propellant_mass = s->propellant_mass + 0.5 * dt * k1[6];
    if (tmp.propellant_mass < 0.0) tmp.propellant_mass = 0.0;
    compute_derivatives_c(&tmp, v, u, k2);

    tmp.x = s->x + 0.5 * dt * k2[0];
    tmp.z = s->z + 0.5 * dt * k2[1];
    tmp.vx = s->vx + 0.5 * dt * k2[2];
    tmp.vz = s->vz + 0.5 * dt * k2[3];
    tmp.theta = s->theta + 0.5 * dt * k2[4];
    tmp.omega = s->omega + 0.5 * dt * k2[5];
    tmp.propellant_mass = s->propellant_mass + 0.5 * dt * k2[6];
    if (tmp.propellant_mass < 0.0) tmp.propellant_mass = 0.0;
    compute_derivatives_c(&tmp, v, u, k3);

    tmp.x = s->x + dt * k3[0];
    tmp.z = s->z + dt * k3[1];
    tmp.vx = s->vx + dt * k3[2];
    tmp.vz = s->vz + dt * k3[3];
    tmp.theta = s->theta + dt * k3[4];
    tmp.omega = s->omega + dt * k3[5];
    tmp.propellant_mass = s->propellant_mass + dt * k3[6];
    if (tmp.propellant_mass < 0.0) tmp.propellant_mass = 0.0;
    compute_derivatives_c(&tmp, v, u, k4);

    s->x += (dt / 6.0) * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0]);
    s->z += (dt / 6.0) * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1]);
    s->vx += (dt / 6.0) * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2]);
    s->vz += (dt / 6.0) * (k1[3] + 2.0 * k2[3] + 2.0 * k3[3] + k4[3]);
    s->theta += (dt / 6.0) * (k1[4] + 2.0 * k2[4] + 2.0 * k3[4] + k4[4]);
    s->omega += (dt / 6.0) * (k1[5] + 2.0 * k2[5] + 2.0 * k3[5] + k4[5]);
    s->propellant_mass += (dt / 6.0) * (k1[6] + 2.0 * k2[6] + 2.0 * k3[6] + k4[6]);
    if (s->propellant_mass < 0.0) s->propellant_mass = 0.0;
}
