package abm.models.maryland;

import abm.data.plans.Purpose;
import abm.data.pop.Person;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Occupation;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

/**
 * RTS-empirical WEEKLY activity generator that is calibrated so a single representative WEEKDAY,
 * extracted downstream (see validation/abit_day.py), reproduces the RTS DAILY tour distribution.
 *
 * ABIT is a weekly model: {@link #calculateNumberOfActivitiesPerWeek} returns a per-WEEK count that
 * the day-of-week assignment spreads across the 7-day diary, and a representative weekday is then
 * pulled out. The RTS coefficient file (rt_freq_rates.csv) holds tours/person/DAY, so those daily
 * rates must be converted to WEEKLY rates before feeding this method (the historical bug fed the raw
 * daily rate as if it were weekly, yielding ~1.4 tours per WHOLE WEEK, hence ~1 tour on a
 * representative weekday and WORK badly under-generated).
 *
 * Conversion used here (calibrated against the RTS daily by-purpose mix, WORK 0.54 / SHOP 0.27 /
 * OTHER 0.56 tours per traveler-day, count distribution ~71/22/6/1):
 *   - WORK (mandatory, gated to EMPLOYED): returns {@link #WORK_DAYS_PER_WEEK} = 5, i.e. a work tour
 *     on every weekday. {@link MarylandDayOfWeekMandatoryAssignment} concentrates those five workdays
 *     on Mon-Fri, so a worker has a work tour on essentially every weekday and the representative
 *     weekday always carries the commute.
 *   - EDUCATION: 0 (SILO has no schools; no mandatory school tours are generated).
 *   - Discretionary (SHOP/OTHER/RECREATION/ACCOMPANY): Poisson(daily x {@link #WEEKDAY_WEEKLY_FACTOR}),
 *     scattered by {@link MarylandDayOfWeekDiscretionaryAssignment} over the five weekdays (Poisson
 *     thinning -> ~Poisson(daily) per weekday), so the representative weekday reproduces the RTS daily
 *     shop/other rate. The 6.0 factor is the empirically calibrated value (a naive daily x 7 over-
 *     generates once the representative-weekday is extracted).
 */
public class MarylandFrequencyGenerator implements FrequencyGenerator {

    private static final Map<Purpose, Double> baseRate = new HashMap<>();
    private static boolean loaded = false;
    private final Random rnd = AbitUtils.getRandomObject();
    // an EMPLOYED person makes a work tour on every weekday (Mon-Fri); the mandatory day-of-week
    // assignment places these 5 workdays on the 5 weekdays.
    private static final int WORK_DAYS_PER_WEEK = 5;
    // daily->weekly conversion for discretionary purposes, calibrated PER PURPOSE against the RTS daily
    // by-purpose tour mix (see class javadoc; SHOP is slightly higher than the others). The
    // discretionary tours are concentrated on the representative weekday
    // (MarylandDayOfWeekDiscretionaryAssignment), so these factors size the daily bundle that day
    // carries. They absorb (a) the ~2x per-capita volume needed because a work-tour-every-weekday
    // population has ~2x the RTS pooled-day traveler pool, and (b) the ~40% of discretionary tours
    // dropped by destination choice for unreachable zones. Overridable via -D for recalibration.
    private static final double F_SHOP =
            Double.parseDouble(System.getProperty("abit.disc.factor.shop", "5.7"));
    private static final double F_OTHER =
            Double.parseDouble(System.getProperty("abit.disc.factor.other", "5.2"));
    private static double discFactor(Purpose purpose) {
        return purpose == Purpose.SHOPPING ? F_SHOP : F_OTHER;
    }

    public MarylandFrequencyGenerator() {
        if (!loaded) load();
    }

    private static synchronized void load() {
        if (loaded) return;
        String f = AbitResources.instance.getString("rt.freq.rates");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                baseRate.put(Purpose.valueOf(r[0].trim().toUpperCase()), Double.parseDouble(r[1].trim()));
            }
        } catch (Exception e) {
            throw new RuntimeException("MarylandFrequencyGenerator load failed", e);
        }
        loaded = true;
    }

    @Override
    public int calculateNumberOfActivitiesPerWeek(Person person, Purpose purpose) {
        Occupation occ = person.getOccupation();
        if (purpose == Purpose.EDUCATION) {
            return 0;   // EDUCATION dropped: SILO has no schools, so no mandatory school tours are generated
        }
        if (purpose == Purpose.WORK) {
            // an EMPLOYED person works every weekday -> return the number of weekdays; the mandatory
            // day-of-week assignment places these on Mon-Fri (distinct days). Others: no work tour.
            return occ == Occupation.EMPLOYED ? WORK_DAYS_PER_WEEK : 0;
        }
        // discretionary: feed a WEEKLY rate = RTS daily rate x weekday factor; the discretionary
        // day-of-week assignment scatters them over the weekdays so a single representative weekday
        // reproduces the RTS daily rate for this purpose.
        if (occ == Occupation.TODDLER) return 0;
        double rate = baseRate.getOrDefault(purpose, 0.0) * discFactor(purpose);
        return poisson(rate);
    }

    private int poisson(double lambda) {
        if (lambda <= 0) return 0;
        double l = Math.exp(-lambda), p = 1.0;
        int k = 0;
        do { k++; p *= rnd.nextDouble(); } while (p > l);
        return k - 1;
    }
}
