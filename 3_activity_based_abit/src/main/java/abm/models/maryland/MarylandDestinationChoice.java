package abm.models.maryland;

import abm.data.DataSet;
import abm.data.geo.Location;
import abm.data.geo.MicroscopicLocation;
import abm.data.geo.Zone;
import abm.data.plans.Activity;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Person;
import abm.models.destinationChoice.DestinationChoice;
import abm.properties.AbitResources;
import abm.properties.InternalProperties;
import abm.utils.AbitUtils;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.*;

/**
 * LOS-SENSITIVE gravity destination choice (Tour-Based MITO #02). The destination zone j is drawn with
 * probability  P(j|i) proportional to  attraction_j * f(t_ij),  where t_ij is the real car TIME skim
 * (so a congested/tolled skim shifts destinations closer — the property required for the I-695 study).
 *
 * Trip-length long-tail fix: f is a TWO-COMPONENT friction of travel time,
 *     f(t) = (t+1)^b_logtime * exp(b_time*t)  +  w2 * (t+1)^p2 * exp(b2*t),
 * fit jointly (per discretionary purpose) to the cleaned-RTS median AND mean AND CDF tail. The steep
 * first term sets the short-range bulk (median); the shallower-decay second term supplies the fat
 * long-trip tail that a single Tanner cannot reach without over-lengthening the median (it caps the
 * mean/median skew near ~1.4, but RTS SHOP/OTHER need ~1.8-2.1). Because BOTH terms decay in t, the
 * friction stays LOS-sensitive — a congested/tolled skim shifts destinations closer and the mean drops
 * (verified: skim x1.5 -> mean drops ~9-20%). Coefficients: input/maryland/coef/dest_friction_power.csv
 * (columns purpose,b_logtime,b_time,w2,p2,b2; w2=0 => single Tanner, e.g. WORK). No fixed empirical-
 * distance sampling is used, so destination choice remains fully impedance-driven.
 *
 * Per-(home-zone x purpose) sampling CDFs are cached. A static timeScale (dest.time.scale, default 1.0)
 * multiplies skim time for the congestion/LOS-sensitivity test.
 */
public class MarylandDestinationChoice implements DestinationChoice {

    private static final Map<Purpose, Double> bLogTime = new HashMap<>();
    private static final Map<Purpose, Double> bTime = new HashMap<>();
    // Optional second friction component (fat long-trip tail): w2 * (t+1)^p2 * exp(b2*t).
    // When w2 == 0 the friction reduces to the single-term Tanner (backward compatible).
    private static final Map<Purpose, Double> tailW = new HashMap<>();
    private static final Map<Purpose, Double> tailLogTime = new HashMap<>();
    private static final Map<Purpose, Double> tailTime = new HashMap<>();
    private static boolean loaded = false;
    private static volatile double timeScale = 1.0;

    private final DataSet dataSet;
    private final List<Zone> zones;
    private final int[] zoneIds;
    private final double[] attr;
    private final MicroscopicLocation[] zoneLoc;
    private final Random rnd = AbitUtils.getRandomObject();
    // cache: homeZoneId -> purpose -> cumulative weights over zones
    private final Map<Long, double[]> cache = new java.util.concurrent.ConcurrentHashMap<>();

    public MarylandDestinationChoice(DataSet dataSet) {
        this.dataSet = dataSet;
        this.zones = new ArrayList<>(dataSet.getZones().values());
        this.zoneIds = new int[zones.size()];
        this.attr = new double[zones.size()];
        this.zoneLoc = new MicroscopicLocation[zones.size()];
        for (int i = 0; i < zones.size(); i++) {
            Zone z = zones.get(i);
            zoneIds[i] = z.getZoneId();
            // discretionary attraction is population-dominant (retail/services follow residents and are
            // spatially distributed) so short local trips are reproduced; jobs down-weighted so shopping/
            // other are not all pulled to the (few) high-employment downtown zones.
            attr[i] = 1.0
                    + z.getAttribute("hh.total").map(o -> (double) ((Integer) o)).orElse(0.0)
                    + 0.25 * z.getAttribute("jj.total").map(o -> (double) ((Integer) o)).orElse(0.0);
            double x = z.getAttribute("x").map(o -> (double) o).orElse(0.0);
            double y = z.getAttribute("y").map(o -> (double) o).orElse(0.0);
            MicroscopicLocation l = new MicroscopicLocation(x, y);
            l.setZone(z);
            zoneLoc[i] = l;
        }
        if (!loaded) load();
    }

    public static void setTimeScale(double s) { timeScale = s; }

    private static synchronized void load() {
        if (loaded) return;
        String f = AbitResources.instance.getString("dest.power.friction");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                Purpose p = Purpose.valueOf(r[0].trim().toUpperCase());
                bLogTime.put(p, Double.parseDouble(r[1].trim()));
                bTime.put(p, r.length > 2 ? Double.parseDouble(r[2].trim()) : 0.0);
                tailW.put(p, r.length > 3 ? Double.parseDouble(r[3].trim()) : 0.0);
                tailLogTime.put(p, r.length > 4 ? Double.parseDouble(r[4].trim()) : 0.0);
                tailTime.put(p, r.length > 5 ? Double.parseDouble(r[5].trim()) : 0.0);
            }
        } catch (Exception e) {
            throw new RuntimeException("dest.power.friction load failed", e);
        }
        try { timeScale = AbitResources.instance.getDouble("dest.time.scale", 1.0); } catch (Exception ignored) {}
        loaded = true;
    }

    private double[] cdfFor(Location home, Purpose purpose) {
        double blt = bLogTime.getOrDefault(purpose, bLogTime.getOrDefault(Purpose.OTHER, -1.3));
        double bt = bTime.getOrDefault(purpose, bTime.getOrDefault(Purpose.OTHER, -0.055));
        double w2 = tailW.getOrDefault(purpose, tailW.getOrDefault(Purpose.OTHER, 0.0));
        double p2 = tailLogTime.getOrDefault(purpose, tailLogTime.getOrDefault(Purpose.OTHER, 0.0));
        double b2 = tailTime.getOrDefault(purpose, tailTime.getOrDefault(Purpose.OTHER, 0.0));
        long key = ((long) home.getZoneId() << 8) ^ purpose.ordinal();
        double[] cached = cache.get(key);
        if (cached != null) return cached;
        double[] cum = new double[zones.size()];
        double run = 0;
        for (int i = 0; i < zones.size(); i++) {
            double t = dataSet.getTravelTimes().getTravelTimeInMinutes(home, zoneLoc[i], Mode.CAR_DRIVER, InternalProperties.PEAK_HOUR_MIN);
            if (!(t >= 0) || t > 600) t = 600;
            t *= timeScale;
            // Two-component LOS-sensitive friction:
            //   f = (t+1)^blt * exp(bt*t)  +  w2 * (t+1)^p2 * exp(b2*t)
            // Term 1 is a steep Tanner that sets the short-range bulk (the trip-length MEDIAN); term 2 is a
            // shallower-decay power/exp tail that supplies the fat long-trip tail (the trip-length MEAN /
            // regional VMT). BOTH terms decay in travel time, so a slower/congested/tolled skim still
            // shifts destinations closer (mean drops) — the LOS-sensitivity the I-695 study needs. When
            // w2 == 0 this reduces to the original single Tanner.
            double fr = Math.pow(t + 1.0, blt) * Math.exp(bt * t);
            if (w2 != 0.0) fr += w2 * Math.pow(t + 1.0, p2) * Math.exp(b2 * t);
            run += attr[i] * fr;
            cum[i] = run;
        }
        cache.put(key, cum);
        return cum;
    }

    @Override
    public void selectMainActivityDestination(Person person, Activity activity) {
        Location home = person.getHousehold().getLocation();
        double[] cum = cdfFor(home, activity.getPurpose());
        double total = cum[cum.length - 1];
        int sel;
        if (total <= 0) { sel = rnd.nextInt(zones.size()); }
        else {
            double u = rnd.nextDouble() * total;
            int lo = 0, hi = cum.length - 1;
            while (lo < hi) { int m = (lo + hi) >>> 1; if (cum[m] < u) lo = m + 1; else hi = m; }
            sel = lo;
        }
        activity.setLocation(jitter(zones.get(sel)));
    }

    @Override
    public void selectStopDestination(Person person, Tour tour, Activity activity) {
        // stop near an attraction-weighted zone (short detour)
        int sel = rnd.nextInt(zones.size());
        activity.setLocation(jitter(zones.get(sel)));
    }

    private MicroscopicLocation jitter(Zone z) {
        double x = z.getAttribute("x").map(o -> (double) o).orElse(0.0);
        double y = z.getAttribute("y").map(o -> (double) o).orElse(0.0);
        MicroscopicLocation loc = new MicroscopicLocation(x + (rnd.nextDouble() - 0.5) * 200, y + (rnd.nextDouble() - 0.5) * 200);
        loc.setZone(z);
        return loc;
    }
}
