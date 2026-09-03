//! A cell under load, worked out in the browser.
//!
//! WHAT THIS IS
//! ------------
//! The website shows what a manufacturer published. This asks the next
//! question -- "what happens if I actually pull 2 C out of it at -10 °C?" --
//! and answers it from those same published numbers.
//!
//! WHAT IT IS NOT
//! --------------
//! It is not a measurement, and the page says so wherever it draws the result.
//! Every input is either a value the datasheet stated or an assumption named
//! in `assumptions()` below. Nothing here is fitted to test data, because the
//! library does not yet hold test data for these cells.
//!
//! THE MODEL
//! ---------
//! One RC-free equivalent circuit, integrated over depth of discharge:
//!
//!     V(t) = OCV(soc) - I · R0(T)
//!
//! * `OCV(soc)` is a normalised open-circuit shape for the chemistry family,
//!   scaled to the cell's own published voltages. Two shapes: the flat LFP
//!   plateau and the sloped NMC/NCA curve. They are tables, not fits.
//! * `R0(T)` is the published internal resistance multiplied by a temperature
//!   factor. Resistance roughly quadruples from 25 °C to -20 °C; the factor
//!   table below says so in seven points and interpolates between them.
//! * Deliverable capacity also falls with temperature, on its own table.
//! * Heat is I²·R0 integrated over the discharge, and the temperature rise is
//!   that heat over the cell's mass at 1000 J/(kg·K) with no cooling -- the
//!   worst case, and the one worth seeing.
//!
//! No transcendental functions, no allocator, no standard library: the whole
//! module is a few kilobytes and starts in under a millisecond.

#![no_std]

use core::panic::PanicInfo;
use core::ptr::addr_of_mut;

#[panic_handler]
fn panic(_: &PanicInfo) -> ! {
    loop {}
}

/// Points on the returned curve.
pub const N: usize = 200;
/// Curve (soc, volts, amps interleaved) followed by the summary scalars.
const LEN: usize = N * 3 + 16;

static mut OUT: [f32; LEN] = [0.0; LEN];

/// Normalised open-circuit voltage, 0 % to 100 % state of charge in 11 steps.
/// Flat where the chemistry is flat; the LFP plateau is the whole point of it.
const OCV_LFP: [f32; 11] = [0.00, 0.62, 0.74, 0.78, 0.80, 0.82, 0.84, 0.86, 0.88, 0.92, 1.00];
const OCV_NMC: [f32; 11] = [0.00, 0.24, 0.38, 0.48, 0.57, 0.65, 0.73, 0.81, 0.88, 0.94, 1.00];

/// Temperature, and what it does to resistance and to available capacity.
const T_PTS: [f32; 7] = [-20.0, -10.0, 0.0, 10.0, 25.0, 40.0, 55.0];
const R_MUL: [f32; 7] = [4.00, 2.60, 1.80, 1.30, 1.00, 0.90, 0.88];
const Q_MUL: [f32; 7] = [0.65, 0.80, 0.88, 0.95, 1.00, 1.00, 0.98];

/// Specific heat of a lithium-ion cell, J/(kg·K). An assumption, and a common
/// one: real values sit between 900 and 1100 for most formats.
const CP: f32 = 1000.0;

fn lerp_table(x: f32, xs: &[f32], ys: &[f32]) -> f32 {
    if x <= xs[0] {
        return ys[0];
    }
    let last = xs.len() - 1;
    if x >= xs[last] {
        return ys[last];
    }
    let mut i = 0;
    while i < last && x > xs[i + 1] {
        i += 1;
    }
    let t = (x - xs[i]) / (xs[i + 1] - xs[i]);
    ys[i] + (ys[i + 1] - ys[i]) * t
}

/// The open-circuit shape at a state of charge, 0.0 to 1.0.
fn ocv_shape(soc: f32, flat: bool) -> f32 {
    let table = if flat { &OCV_LFP } else { &OCV_NMC };
    let s = if soc < 0.0 { 0.0 } else if soc > 1.0 { 1.0 } else { soc };
    let p = s * 10.0;
    let i = p as usize;
    if i >= 10 {
        return table[10];
    }
    table[i] + (table[i + 1] - table[i]) * (p - i as f32)
}

/// Run one discharge.
///
/// `flat` selects the LFP plateau over the sloped curve. `r_mohm` may be zero,
/// in which case the caller has told the reader that the value was assumed.
/// Returns the number of curve points written.
///
/// The output buffer holds, in order:
///   `[0 .. n)`         depth of discharge, 0 to 1
///   `[N .. N+n)`       terminal voltage, V
///   `[2N .. 2N+n)`     cell temperature, °C
///   `[3N + 0]`         delivered capacity, Ah
///   `[3N + 1]`         delivered energy, Wh
///   `[3N + 2]`         specific energy, Wh/kg
///   `[3N + 3]`         run time, seconds
///   `[3N + 4]`         mean voltage, V
///   `[3N + 5]`         heat, Wh
///   `[3N + 6]`         temperature rise, K
///   `[3N + 7]`         fraction of the rated capacity delivered
///   `[3N + 8]`         current, A
#[no_mangle]
pub extern "C" fn simulate(
    cap_ah: f32,
    v_max: f32,
    v_min: f32,
    r_mohm: f32,
    mass_g: f32,
    c_rate: f32,
    temp_c: f32,
    flat: i32,
) -> i32 {
    let flat = flat != 0;
    let cap = if cap_ah > 0.0 { cap_ah } else { 1.0 };
    let usable = cap * lerp_table(temp_c, &T_PTS, &Q_MUL);
    let r = (if r_mohm > 0.0 { r_mohm } else { 1.0 }) * 0.001
        * lerp_table(temp_c, &T_PTS, &R_MUL);
    let i_a = cap * c_rate;
    let mass_kg = if mass_g > 0.0 { mass_g * 0.001 } else { 0.0 };

    let span = if v_max > v_min { v_max - v_min } else { 1.0 };
    let dsoc = 1.0 / (N - 1) as f32;

    let mut ah = 0.0f32;
    let mut wh = 0.0f32;
    let mut heat_wh = 0.0f32;
    let mut t_cell = temp_c;
    let mut n = 0usize;

    let mut k = 0usize;
    while k < N {
        let soc = 1.0 - k as f32 * dsoc;
        let ocv = v_min + span * ocv_shape(soc, flat);
        let v = ocv - i_a * r;
        if v < v_min && k > 0 {
            break;                       // the cut-off the datasheet gave
        }
        let step_ah = usable * dsoc;     // charge moved in this step
        let hours = if i_a > 0.0 { step_ah / i_a } else { 0.0 };
        ah += step_ah;
        wh += v * step_ah;
        let q = i_a * i_a * r * hours;   // I²R, in watt-hours
        heat_wh += q;
        if mass_kg > 0.0 {
            t_cell += q * 3600.0 / (mass_kg * CP);
        }

        let idx = k;
        unsafe {
            let p = addr_of_mut!(OUT) as *mut f32;
            *p.add(idx) = 1.0 - soc;
            *p.add(N + idx) = v;
            *p.add(2 * N + idx) = t_cell;
        }
        n = k + 1;
        k += 1;
    }

    let secs = if i_a > 0.0 { ah / i_a * 3600.0 } else { 0.0 };
    let summary = [
        ah,
        wh,
        if mass_kg > 0.0 { wh / mass_kg } else { 0.0 },
        secs,
        if ah > 0.0 { wh / ah } else { 0.0 },
        heat_wh,
        t_cell - temp_c,
        if cap > 0.0 { ah / cap } else { 0.0 },
        i_a,
    ];
    unsafe {
        let p = addr_of_mut!(OUT) as *mut f32;
        let mut j = 0;
        while j < summary.len() {
            *p.add(3 * N + j) = summary[j];
            j += 1;
        }
    }
    n as i32
}

/// Where the results are, and how much room they take.
#[no_mangle]
pub extern "C" fn out_ptr() -> *const f32 {
    addr_of_mut!(OUT) as *const f32
}

#[no_mangle]
pub extern "C" fn points() -> i32 {
    N as i32
}
