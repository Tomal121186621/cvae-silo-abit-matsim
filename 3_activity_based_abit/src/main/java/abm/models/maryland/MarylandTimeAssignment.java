package abm.models.maryland;

import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.models.activityGeneration.time.TimeAssignment;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;

import java.io.BufferedReader;
import java.io.FileReader;
import java.time.DayOfWeek;
import java.util.*;

/**
 * RTS-empirical time-of-day + duration assignment (replaces the Simple assignment, which piled starts at
 * midnight — it sliced a single-day TOD distribution by week-day — and used a constant 160-min duration).
 *
 * Start time: sampled from the RTS purpose-specific departure distribution (tod_rts.csv, 0..1440 min),
 * giving work AM-out / PM-return and midday-spread discretionary peaks.
 * Duration: sampled from the RTS purpose-specific activity-duration distribution (duration.distributions.csv):
 * work ~8 h, education ~7 h, shopping ~0.5 h, other ~1 h, etc.
 * Times are stored as week-minutes (dayOfWeek offset + time-of-day) so tours on different assigned days do
 * not overlap; the single representative weekday is recovered by (time mod 1440).
 */
public class MarylandTimeAssignment implements TimeAssignment {

    private static final Map<Purpose, double[]> startCdf = new HashMap<>();   // index = minute/STEP -> cumulative
    private static final Map<Purpose, double[]> durCdf = new HashMap<>();
    private static final int STEP = 15;
    private static boolean loaded = false;
    private final Random rnd = AbitUtils.getRandomObject();

    public MarylandTimeAssignment() {
        if (!loaded) load();
    }

    private static synchronized void load() {
        if (loaded) return;
        readDist(AbitResources.instance.getString("tod.dummy.file"), "time", "purpose", "probability", startCdf, 1440);
        readDist(AbitResources.instance.getString("duration.distributions"), "duration_min", "purpose", "duration_prob", durCdf, 1440);
        loaded = true;
    }

    private static void readDist(String file, String tcol, String pcol, String vcol, Map<Purpose, double[]> out, int maxMin) {
        Map<Purpose, double[]> acc = new HashMap<>();
        int n = maxMin / STEP + 1;
        try (BufferedReader br = new BufferedReader(new FileReader(file))) {
            String[] h = br.readLine().split(",");
            int it = idx(h, tcol), ip = idx(h, pcol), iv = idx(h, vcol);
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                Purpose p;
                try { p = Purpose.valueOf(r[ip].trim().toUpperCase()); } catch (Exception e) { continue; }
                int minute = (int) Double.parseDouble(r[it].trim());
                int bin = Math.min(n - 1, Math.max(0, minute / STEP));
                double prob = Double.parseDouble(r[iv].trim());
                acc.computeIfAbsent(p, k -> new double[n])[bin] += prob;
            }
        } catch (Exception e) {
            throw new RuntimeException("MarylandTimeAssignment dist load failed: " + file, e);
        }
        for (Map.Entry<Purpose, double[]> e : acc.entrySet()) {
            double[] pdf = e.getValue(), cdf = new double[pdf.length];
            double run = 0, tot = 0;
            for (double v : pdf) tot += v;
            if (tot <= 0) { for (int i = 0; i < cdf.length; i++) cdf[i] = (i + 1.0) / cdf.length; }
            else { for (int i = 0; i < pdf.length; i++) { run += pdf[i] / tot; cdf[i] = run; } }
            out.put(e.getKey(), cdf);
        }
    }

    private int sample(Map<Purpose, double[]> m, Purpose p, int fallback) {
        double[] cdf = m.get(p);
        if (cdf == null) cdf = m.getOrDefault(Purpose.OTHER, null);
        if (cdf == null) return fallback;
        double u = rnd.nextDouble();
        int lo = 0, hi = cdf.length - 1;
        while (lo < hi) { int mid = (lo + hi) >>> 1; if (cdf[mid] < u) lo = mid + 1; else hi = mid; }
        return lo * STEP + rnd.nextInt(STEP);
    }

    @Override
    public void assignStartTimeAndDuration(Activity activity) {
        DayOfWeek d = activity.getDayOfWeek();
        int off = (d == null ? 0 : d.ordinal()) * 1440;
        int start = sample(startCdf, activity.getPurpose(), 480);
        int dur = Math.max(15, sample(durCdf, activity.getPurpose(), 60));
        activity.setStartTime_min(off + start);
        activity.setEndTime_min(off + start + dur);
    }

    @Override
    public void assignDurationToStop(Activity activity) {
        int off = (activity.getDayOfWeek() == null ? 0 : activity.getDayOfWeek().ordinal()) * 1440;
        int dur;
        switch (activity.getPurpose()) {
            case SHOPPING: dur = 30; break;
            case RECREATION: dur = 60; break;
            case ACCOMPANY: dur = 10; break;
            default: dur = 15;
        }
        activity.setStartTime_min(off);
        activity.setEndTime_min(off + dur);
    }

    @Override
    public void assignDurationAndThenStartTime(Activity activity) {
        assignStartTimeAndDuration(activity);
    }

    private static int idx(String[] header, String name) {
        for (int i = 0; i < header.length; i++) if (header[i].trim().equalsIgnoreCase(name)) return i;
        throw new RuntimeException("Column '" + name + "' not found");
    }
}
