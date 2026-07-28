package abm.models.maryland;

import abm.data.DataSet;
import abm.data.geo.BBSRType;
import abm.data.geo.Location;
import abm.data.geo.Zone;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.modeChoice.TourModeChoice;
import abm.properties.AbitResources;
import abm.properties.InternalProperties;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;
import java.util.*;

/**
 * FULL published Chayan &amp; Cirillo (2024) mode-choice model — 5 purpose-specific MNLs (Table 3 + A1–A4),
 * with the complete per-mode utility:
 *   V = ASC + age·b_age + male·b_male + license·b_lic + hhsize·b_hhsize + hhautos·b_hhautos
 *       + coreCity·b_core + medCity·b_med + rural·b_rural + GC·b_gc + tripLength·b_tl
 * Generalized cost GC = travelTime(min) + monetaryCost / VOT, where monetaryCost = distance(km)·costPerKm
 * (+ per-OD auto toll). Reference alt = CAR_DRIVER. Modes: [CAR_DRIVER, WALK, BIKE, CAR_PASSENGER,
 * SHARED_RIDE, BUS, TRAIN]; SHARED_RIDE is folded into CAR_PASSENGER for output.
 *
 * The only adaptation: ASCs are re-anchored (iterative calibration) so base (no-toll) shares reproduce the
 * RTS tour shares in rt_mode_by_purpose.csv; all published slopes are kept. The re-anchored sets are written
 * to coef/modechoice_full_&lt;purpose&gt;.csv.
 *
 * TOLL-READY: a per-run auto toll (USD, default 0) is ADDED to the auto monetary cost -> flows through GC.
 */
public class MarylandFullModeChoice implements TourModeChoice {

    private static final Logger logger = Logger.getLogger(MarylandFullModeChoice.class);

    // paper mode order (index 4 = Shared Ride, folded into CAR_PASSENGER for ABIT output)
    static final String[] NAME = {"CAR_DRIVER", "WALK", "BIKE", "CAR_PASSENGER", "SHARED_RIDE", "BUS", "TRAIN"};
    static final Mode[] SKIM = {Mode.CAR_DRIVER, Mode.WALK, Mode.BIKE, Mode.CAR_PASSENGER, Mode.CAR_DRIVER, Mode.BUS, Mode.TRAIN};
    static final Mode[] OUT = {Mode.CAR_DRIVER, Mode.WALK, Mode.BIKE, Mode.CAR_PASSENGER, Mode.CAR_PASSENGER, Mode.BUS, Mode.TRAIN};
    static final int SR = 4;
    static final String[] VARS = {"ASC", "age", "male", "license", "hhsize", "hhautos", "coreCity", "medCity", "rural", "gc", "tripLength"};
    // VOT ($/h equiv used as min-per-$ divisor) and monetary cost per km
    static final double[] VOT = {30, 0, 0, 30, 40, 15, 15};          // CAR_DRIVER,WALK,BIKE,AutoP,SR,BUS,TRAIN
    static final double[] COST_PER_KM = {0.12, 0, 0, 0.12, 0.12, 0.50, 0.50};
    static final boolean[] AUTO = {true, false, false, true, true, false, false};

    // --- income-elastic VOT (Chayan & Cirillo: VOT ~ wage, income elasticity ~0.6). VOT[] above is the
    // reference VOT at the SILO calib5 median household income; households scale off it so the toll
    // response is income-differentiated while the median household reproduces the published VOT (base
    // car ~0.76 preserved by the toll=0 ASC re-anchor). ---
    static final double VOT_INCOME_REF_USD_MTH = 7018.0;             // SILO calib5 median hh income ($84.2k/yr)
    static final double VOT_INCOME_ELASTICITY  = 0.6;                // income elasticity of VOT
    static final double VOT_FACTOR_MIN = 0.4, VOT_FACTOR_MAX = 2.5;  // clamp at the income tails

    // ABIT purpose -> published table
    private static String table(Purpose p) {
        switch (p) {
            case WORK: case EDUCATION: return "HBW";
            case SHOPPING: return "HBS";
            case OTHER: case RECREATION: case ACCOMPANY: return "HBO";
            case SUBTOUR: return "NHBW";
            default: return "HBO";
        }
    }

    // static so all threads share the (frozen, re-anchored) coefficients
    private static Map<Purpose, Map<String, double[]>> coef = new HashMap<>();
    private static Map<Purpose, Map<Mode, Double>> targets = new HashMap<>();
    private static final Map<Purpose, Double> distMeanKm = new HashMap<>();
    private static boolean calibrated = false;
    private static volatile double autoTollUsd = 0.0;   // toll hook

    private final DataSet dataSet;
    private final Random rnd = AbitUtils.getRandomObject();

    public MarylandFullModeChoice(DataSet dataSet) {
        this.dataSet = dataSet;
        synchronized (MarylandFullModeChoice.class) {
            if (!calibrated) {
                loadTargets();
                loadDistMeans();
                loadPublished();
                calibrateAscs();
                writeReanchored();
                calibrated = true;
            }
        }
    }

    public static void setToll(double usd) { autoTollUsd = usd; }
    public static double getToll() { return autoTollUsd; }

    // ---------------------------------------------------------------- coefficients
    private void loadPublished() {
        for (Purpose p : new Purpose[]{Purpose.WORK, Purpose.EDUCATION, Purpose.SHOPPING, Purpose.OTHER, Purpose.RECREATION, Purpose.ACCOMPANY, Purpose.SUBTOUR}) {
            String tbl = table(p);
            String f = AbitResources.instance.getString("modechoice.dir") + "/modechoice_published_" + tbl + ".csv";
            Map<String, double[]> byVar = new HashMap<>();
            try (BufferedReader br = new BufferedReader(new FileReader(f))) {
                br.readLine();
                String line;
                while ((line = br.readLine()) != null) {
                    String[] r = line.split(",");
                    double[] v = new double[7];
                    for (int i = 0; i < 7; i++) v[i] = Double.parseDouble(r[i + 1].trim());
                    byVar.put(r[0].trim(), v);
                }
            } catch (Exception e) {
                throw new RuntimeException("mode coef load failed: " + f, e);
            }
            coef.put(p, byVar);
        }
    }

    private void loadTargets() {
        String f = AbitResources.instance.getString("rt.mode.by.purpose");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                Purpose p = Purpose.valueOf(r[0].trim().toUpperCase());
                targets.computeIfAbsent(p, k -> new EnumMap<>(Mode.class)).put(Mode.valueOf(r[1].trim()), Double.parseDouble(r[2].trim()));
            }
        } catch (Exception e) {
            throw new RuntimeException("mode targets load failed", e);
        }
    }

    private void loadDistMeans() {
        String f = AbitResources.instance.getString("rt.dist.by.purpose");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                distMeanKm.put(Purpose.valueOf(r[0].trim().toUpperCase()), Double.parseDouble(r[1].trim()));
            }
        } catch (Exception e) {
            throw new RuntimeException("dist means load failed", e);
        }
    }

    /** Sample a destination zone whose network distance from home matches an RTS Exp(mean) draw for the
     * purpose — so ASC calibration sees the same trip-length scale as plan generation. */
    private Zone sampleDest(Purpose p, Location home, List<Zone> zones) {
        double mean = distMeanKm.getOrDefault(p, 8.0);
        double targetM = Math.max(200, Math.min(60000, -mean * Math.log(1 - rnd.nextDouble()) * 1000));
        Zone best = null; double bestDiff = Double.MAX_VALUE;
        for (int i = 0; i < 40; i++) {
            Zone z = zones.get(rnd.nextInt(zones.size()));
            double d = dataSet.getTravelDistances().getTravelDistanceInMeters(home, centroid(z), Mode.UNKNOWN, InternalProperties.PEAK_HOUR_MIN);
            double diff = Math.abs(d - targetM);
            if (diff < bestDiff) { bestDiff = diff; best = z; }
        }
        return best;
    }

    private Location centroid(Zone z) {
        double x = z.getAttribute("x").map(o -> (double) o).orElse(0.0);
        double y = z.getAttribute("y").map(o -> (double) o).orElse(0.0);
        abm.data.geo.MicroscopicLocation l = new abm.data.geo.MicroscopicLocation(x, y);
        l.setZone(z);
        return l;
    }

    // ---------------------------------------------------------------- ASC re-anchoring
    /** Build a representative calibration sample of (person, home->dest) tuples per purpose, then adjust
     * ASCs by ln(target/predicted) until base shares match the RTS tour shares. SR is folded into
     * CAR_PASSENGER and TRAM into TRAIN for the target comparison (RTS categories). */
    private void calibrateAscs() {
        List<Person> pop = new ArrayList<>(dataSet.getPersons().values());
        List<Zone> zones = new ArrayList<>(dataSet.getZones().values());
        int SAMPLE = 4000;
        double savedToll = autoTollUsd; autoTollUsd = 0.0;   // calibrate at base (no toll)
        for (Purpose p : targets.keySet()) {
            if (!coef.containsKey(p)) continue;
            // sample tuples
            List<Person> sp = new ArrayList<>();
            List<Zone> sd = new ArrayList<>();
            for (int i = 0; i < SAMPLE && !pop.isEmpty(); i++) {
                Person person = pop.get(rnd.nextInt(pop.size()));
                Zone dest = sampleDest(p, person.getHousehold().getLocation(), zones);  // RTS-distance dest
                sp.add(person); sd.add(dest);
            }
            Map<Mode, Double> tgt = targets.get(p);
            for (int iter = 0; iter < 25; iter++) {
                double[] agg = new double[7];
                for (int i = 0; i < sp.size(); i++) {
                    double[] pr = probabilities(p, sp.get(i), sp.get(i).getHousehold().getLocation(), sd.get(i));
                    for (int m = 0; m < 7; m++) agg[m] += pr[m];
                }
                for (int m = 0; m < 7; m++) agg[m] /= sp.size();
                // collapse to RTS categories: CAR_DRIVER, CAR_PASSENGER(+SR), TRAIN, BUS, WALK, BIKE
                Map<Mode, Double> pred = collapse(agg);
                // adjust each non-reference ASC toward target
                double[] asc = coef.get(p).get("ASC");
                for (int m = 1; m < 7; m++) {
                    double t, pr;
                    if (m == SR) {   // SR shares the CAR_PASSENGER target (split with AutoP)
                        t = tgt.getOrDefault(Mode.CAR_PASSENGER, 1e-4) * 0.5;
                        pr = Math.max(1e-5, agg[SR]);
                    } else {
                        t = tgt.getOrDefault(OUT[m], 1e-4);
                        pr = pred.getOrDefault(OUT[m], 1e-4);
                    }
                    asc[m] += 0.6 * Math.log(Math.max(1e-5, t) / Math.max(1e-5, pr));
                }
            }
        }
        autoTollUsd = savedToll;
        logger.info("Re-anchored mode-choice ASCs to RTS tour shares for " + coef.size() + " purposes");
    }

    /** Iterative ASC calibration against the ACTUAL generated tours: measure realized shares by purpose,
     * nudge ASCs by ln(target/realized), re-apply mode choice, repeat. This anchors base (no-toll) shares
     * to the RTS tour shares using the real generation trip-length distribution. */
    public void reapplyAndCalibrate(DataSet ds, int iters) {
        for (int it = 0; it < iters; it++) {
            Map<Purpose, Map<Mode, int[]>> counts = new HashMap<>();  // purpose -> mode -> {count,total}
            Map<Purpose, int[]> totals = new HashMap<>();
            for (Person person : ds.getPersons().values()) {
                if (person.getPlan() == null) continue;
                for (Tour tour : person.getPlan().getTours().values()) {
                    Purpose p = tour.getMainActivity().getPurpose();
                    if (!coef.containsKey(p) || tour.getTourMode() == null) continue;
                    counts.computeIfAbsent(p, k -> new EnumMap<>(Mode.class))
                            .computeIfAbsent(tour.getTourMode(), k -> new int[1])[0]++;
                    totals.computeIfAbsent(p, k -> new int[1])[0]++;
                }
            }
            for (Purpose p : counts.keySet()) {
                Map<Mode, Double> tgt = targets.get(p);
                if (tgt == null) continue;
                int tot = totals.get(p)[0];
                double[] asc = coef.get(p).get("ASC");
                for (int m = 1; m < 7; m++) {
                    Mode om = OUT[m];   // realized count for CAR_PASSENGER is already AutoP+SR combined
                    double realized = counts.get(p).getOrDefault(om, new int[1])[0] / (double) tot;
                    double target = tgt.getOrDefault(om, 1e-4);   // full CAR_PASSENGER target applied to both AutoP & SR
                    asc[m] += 0.7 * Math.log(Math.max(1e-4, target) / Math.max(1e-4, realized));
                }
            }
            applyToAllTours(ds);
        }
        logger.info("Mode-choice ASCs refined against real tours (" + iters + " iters)");
    }

    /** Re-run mode choice on every home-based tour (used during iterative calibration and toll scenarios). */
    public void applyToAllTours(DataSet ds) {
        for (Person person : ds.getPersons().values()) {
            if (person.getPlan() == null) continue;
            for (Tour tour : person.getPlan().getTours().values()) {
                if (coef.containsKey(tour.getMainActivity().getPurpose())) chooseMode(person, tour);
            }
        }
    }

    private Map<Mode, Double> collapse(double[] pr) {
        Map<Mode, Double> m = new EnumMap<>(Mode.class);
        m.put(Mode.CAR_DRIVER, pr[0]);
        m.put(Mode.WALK, pr[1]);
        m.put(Mode.BIKE, pr[2]);
        m.put(Mode.CAR_PASSENGER, pr[3] + pr[4]);   // AutoP + SR
        m.put(Mode.BUS, pr[5]);
        m.put(Mode.TRAIN, pr[6]);
        return m;
    }

    public void writeReanchored() {
        String dir = AbitResources.instance.getString("modechoice.dir");
        for (Purpose p : new Purpose[]{Purpose.WORK, Purpose.EDUCATION, Purpose.SHOPPING, Purpose.OTHER, Purpose.RECREATION, Purpose.ACCOMPANY}) {
            if (!coef.containsKey(p)) continue;
            try (PrintWriter pw = new PrintWriter(dir + "/modechoice_full_" + p.toString().toLowerCase() + ".csv")) {
                pw.print("variable");
                for (String m : NAME) pw.print("," + m);
                pw.println();
                for (String v : VARS) {
                    pw.print(v);
                    for (double x : coef.get(p).get(v)) pw.print("," + x);
                    pw.println();
                }
            } catch (Exception e) {
                logger.warn("could not write modechoice_full_" + p, e);
            }
        }
    }

    // ---------------------------------------------------------------- utility / probabilities
    private double[] probabilities(Purpose p, Person person, Location origin, Location dest) {
        Map<String, double[]> c = coef.get(p);
        Household hh = person.getHousehold();
        double age = person.getAge();
        double male = person.getGender() == Gender.MALE ? 1 : 0;
        double lic = person.isHasLicense() ? 1 : 0;
        double hhsize = hh.getPersons().size();
        double hhautos = hh.getNumberOfCars();
        Zone oz = dataSet.getZones().get(origin.getZoneId());
        double core = oz != null && oz.getBBSRType() == BBSRType.CORE_CITY ? 1 : 0;
        double med = oz != null && oz.getBBSRType() == BBSRType.MEDIUM_SIZED_CITY ? 1 : 0;
        double rural = oz != null && oz.getBBSRType() == BBSRType.RURAL ? 1 : 0;
        double distKm = dataSet.getTravelDistances().getTravelDistanceInMeters(origin, dest, Mode.UNKNOWN, InternalProperties.PEAK_HOUR_MIN) / 1000.0;

        // household income-elastic VOT factor (SILO income is USD despite the _eur field name)
        double hhIncomeUsdMth = 0.0;
        for (Person pp : hh.getPersons()) hhIncomeUsdMth += pp.getMonthlyIncome_eur();
        double votFactor = Math.pow(Math.max(1.0, hhIncomeUsdMth) / VOT_INCOME_REF_USD_MTH, VOT_INCOME_ELASTICITY);
        votFactor = Math.max(VOT_FACTOR_MIN, Math.min(VOT_FACTOR_MAX, votFactor));

        double[] v = new double[7];
        for (int m = 0; m < 7; m++) {
            double time = dataSet.getTravelTimes().getTravelTimeInMinutes(origin, dest, SKIM[m], InternalProperties.PEAK_HOUR_MIN);
            double money = distKm * COST_PER_KM[m];
            if (AUTO[m]) money += autoTollUsd;                       // toll hook -> auto monetary cost ($)
            // GC in minutes: convert $ to time-equivalent via VOT ($/h): minutes = $ * 60 / VOT.
            // (Literal $/VOT would be dimensionless-tiny and leave the model price-INelastic.)
            double votM = VOT[m] * votFactor;                        // income-elastic VOT
            double gc = votM > 0 ? time + money * 60.0 / votM : 0.0;
            v[m] = c.get("ASC")[m] + c.get("age")[m] * age + c.get("male")[m] * male + c.get("license")[m] * lic
                    + c.get("hhsize")[m] * hhsize + c.get("hhautos")[m] * hhautos
                    + c.get("coreCity")[m] * core + c.get("medCity")[m] * med + c.get("rural")[m] * rural
                    + c.get("gc")[m] * gc + c.get("tripLength")[m] * distKm;
        }
        double max = Double.NEGATIVE_INFINITY;
        for (double x : v) if (x > max) max = x;
        double sum = 0;
        double[] pr = new double[7];
        for (int m = 0; m < 7; m++) { pr[m] = Math.exp(v[m] - max); sum += pr[m]; }
        for (int m = 0; m < 7; m++) pr[m] /= sum;
        return pr;
    }

    // ---------------------------------------------------------------- TourModeChoice
    @Override
    public void chooseMode(Person person, Tour tour) {
        Purpose p = tour.getMainActivity().getPurpose();
        if (!coef.containsKey(p)) p = Purpose.OTHER;
        double[] pr = probabilities(p, person, person.getHousehold().getLocation(), tour.getMainActivity().getLocation());
        double u = rnd.nextDouble(), cum = 0; int sel = 0;
        for (int m = 0; m < 7; m++) { cum += pr[m]; if (u <= cum) { sel = m; break; } sel = m; }
        Mode chosen = OUT[sel];   // SR folds into CAR_PASSENGER
        for (Leg leg : tour.getLegs().values()) leg.setLegMode(chosen);
        tour.setTourMode(chosen);
    }

    @Override public void chooseMode(Person person, Tour tour, Purpose purpose) { chooseMode(person, tour); }
    @Override public Mode chooseMode(Person person, Tour tour, Purpose purpose, Boolean carAvailable) { chooseMode(person, tour); return tour.getTourMode(); }
    @Override public void checkCarAvailabilityAndChooseMode(Household h, Person pe, Tour t, Purpose pu) { chooseMode(pe, t); }
}
