package abm.models.maryland;

import abm.data.plans.Activity;
import abm.models.activityGeneration.time.DayOfWeekDiscretionaryAssignment;
import abm.utils.AbitUtils;

import java.time.DayOfWeek;

/**
 * Maryland discretionary day-of-week assignment: places discretionary activities on the
 * representative weekday (MONDAY), i.e. the SAME day the downstream single-weekday extraction picks
 * (abit_day.pick_day returns the earliest complete weekday, = Monday, which for a worker is a work
 * day). This realises the RTS "discretionary clustered same-day as work / shop-after-work" pattern:
 * a person's daily discretionary bundle sits on their representative work-weekday.
 *
 * Why concentrate rather than scatter over all five weekdays: with a work tour on every weekday the
 * representative-weekday traveler pool is ~2x the RTS pooled-day pool, so the representative day must
 * carry ~2x the RTS daily discretionary volume for the per-traveler rate to match RTS. Scattering
 * over five days shows only ~1 day's worth on the extracted day and, because adding more scattered
 * discretionary mostly creates NEW (non-worker) travelers, the per-traveler shop/other rate
 * saturates below target. Concentrating the daily bundle on the representative day adds those tours
 * to travelers who are already on the road (shop-after-work), lifting the per-traveler rate without
 * inflating the traveler denominator. {@link MarylandFrequencyGenerator} sizes the weekly count so
 * that, after destination-choice attrition, this day carries the RTS daily by-purpose bundle.
 *
 * The Monday label is immaterial to the deliverable: build_studyarea/build_matsim_pop extract that
 * one day and emit it as a 24h representative-weekday MATSim plan (times spread by the RTS
 * time-of-day model), and MATSim assigns a single 24h day.
 */
public class MarylandDayOfWeekDiscretionaryAssignment implements DayOfWeekDiscretionaryAssignment {

    // fraction of discretionary tours placed on the representative weekday (MONDAY); the remainder
    // scatter over the other weekdays (Tue-Fri). Partial concentration trades off the representative
    // day's discretionary volume (shop-after-work) against the traveler denominator / WORK share.
    private static final double P_MON =
            Double.parseDouble(System.getProperty("abit.disc.pmon", "0.5"));

    @Override
    public void assignDayOfWeek(Activity activity) {
        if (AbitUtils.getRandomObject().nextDouble() < P_MON) {
            activity.setDayOfWeek(DayOfWeek.MONDAY);
        } else {
            activity.setDayOfWeek(DayOfWeek.of(2 + AbitUtils.getRandomObject().nextInt(4))); // TUE..FRI
        }
    }
}
