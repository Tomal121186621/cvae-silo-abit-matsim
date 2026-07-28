package abm;

import abm.data.DataSet;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.io.input.MarylandLosDataReader;
import abm.models.ModelSetup;
import abm.models.ModelSetupMaryland;
import abm.models.PlanGenerator;
import abm.models.maryland.MarylandFullModeChoice;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.util.MitoUtil;
import de.tum.bgu.msm.util.concurrent.ConcurrentExecutor;
import org.apache.log4j.Logger;

import java.io.PrintWriter;
import java.util.*;

/**
 * I-695 toll elasticity test. Builds the population once, calibrates the full Chayan &amp; Cirillo mode
 * choice at base (no toll), records base mode shares, then applies a $2 auto toll (added to auto monetary
 * cost -> generalized cost) and re-runs mode choice with the SAME re-anchored ASCs. Writes base-vs-toll
 * shares and implied arc-elasticities to output/toll_test.csv.
 */
public class RunTollTest {

    private static final Logger logger = Logger.getLogger(RunTollTest.class);
    private static final Mode[] REPORT = {Mode.CAR_DRIVER, Mode.CAR_PASSENGER, Mode.BUS, Mode.TRAIN, Mode.WALK, Mode.BIKE};

    public static void main(String[] args) {
        AbitResources.initializeResources(args[0]);
        MitoUtil.initializeRandomNumber(AbitUtils.getRandomObject());
        double tollAmt = AbitResources.instance.getDouble("toll.test.amount", 2.0);
        int threads = AbitResources.instance.getInt("number.of.threads", 4);

        DataSet dataSet = new MarylandLosDataReader().readData();
        MarylandFullModeChoice.setToll(0.0);
        ModelSetup ms = new ModelSetupMaryland(dataSet);
        MarylandFullModeChoice mc = (MarylandFullModeChoice) ms.getTourModeChoice();

        // generate plans (destinations + initial mode choice)
        ConcurrentExecutor ex = ConcurrentExecutor.fixedPoolService(threads);
        Map<Integer, List<Person>> byThread = new HashMap<>();
        int i = 0;
        for (Household hh : dataSet.getHouseholds().values())
            for (Person p : hh.getPersons()) byThread.computeIfAbsent(i++ % threads, k -> new ArrayList<>()).add(p);
        for (int t = 0; t < threads; t++)
            ex.addTaskToQueue(new PlanGenerator(dataSet, ms, t).setPersons(byThread.getOrDefault(t, new ArrayList<>())));
        ex.execute();

        // base: iterative ASC calibration (no toll), then record shares
        mc.reapplyAndCalibrate(dataSet, 20);
        Map<Purpose, Map<Mode, Double>> base = shares(dataSet);
        Map<Mode, Double> baseAll = sharesAll(dataSet);

        // toll scenario: keep ASCs, add $toll, re-apply mode choice
        MarylandFullModeChoice.setToll(tollAmt);
        mc.applyToAllTours(dataSet);
        Map<Purpose, Map<Mode, Double>> toll = shares(dataSet);
        Map<Mode, Double> tollAll = sharesAll(dataSet);

        String out = AbitResources.instance.getString("base.directory") + "/output/toll_test.csv";
        try (PrintWriter pw = new PrintWriter(out)) {
            pw.println("scope,mode,base_share,toll_share,delta_share,pct_change");
            for (Mode m : REPORT) writeRow(pw, "ALL", m, baseAll, tollAll);
            for (Purpose p : new Purpose[]{Purpose.WORK, Purpose.EDUCATION, Purpose.SHOPPING, Purpose.OTHER})
                if (base.containsKey(p)) for (Mode m : REPORT) writeRow(pw, p.toString(), m, base.get(p), toll.get(p));
            // implied arc elasticity of CAR_DRIVER demand wrt auto out-of-pocket cost (midpoint), avg auto cost ~ $1.4/trip base
            pw.println();
            pw.println("# arc elasticity of CAR_DRIVER share wrt auto cost (midpoint). base auto cost approximated per trip.");
            double baseCostApprox = AbitResources.instance.getDouble("toll.base.autocost", 1.4);
            pw.println("scope,e_cardriver_arc");
            arcRow(pw, "ALL", baseAll, tollAll, tollAmt, baseCostApprox);
            for (Purpose p : new Purpose[]{Purpose.WORK, Purpose.EDUCATION, Purpose.SHOPPING, Purpose.OTHER})
                if (base.containsKey(p)) arcRow(pw, p.toString(), base.get(p), toll.get(p), tollAmt, baseCostApprox);
        } catch (Exception e) {
            logger.error("write toll_test failed", e);
        }
        logger.info("Toll test written. base CAR_DRIVER(all)=" + baseAll.get(Mode.CAR_DRIVER)
                + " -> toll=" + tollAll.get(Mode.CAR_DRIVER));
    }

    private static void writeRow(PrintWriter pw, String scope, Mode m, Map<Mode, Double> b, Map<Mode, Double> t) {
        double bs = b.getOrDefault(m, 0.0), ts = t.getOrDefault(m, 0.0);
        double pct = bs > 0 ? (ts - bs) / bs * 100 : 0;
        pw.printf("%s,%s,%.4f,%.4f,%.4f,%.2f%n", scope, m, bs, ts, ts - bs, pct);
    }

    private static void arcRow(PrintWriter pw, String scope, Map<Mode, Double> b, Map<Mode, Double> t, double toll, double baseCost) {
        double q1 = b.getOrDefault(Mode.CAR_DRIVER, 0.0), q2 = t.getOrDefault(Mode.CAR_DRIVER, 0.0);
        double p1 = baseCost, p2 = baseCost + toll;
        double dq = (q2 - q1) / ((q2 + q1) / 2);
        double dp = (p2 - p1) / ((p2 + p1) / 2);
        pw.printf("%s,%.3f%n", scope, dp != 0 ? dq / dp : 0);
    }

    private static Map<Purpose, Map<Mode, Double>> shares(DataSet ds) {
        Map<Purpose, Map<Mode, double[]>> c = new HashMap<>();
        Map<Purpose, int[]> tot = new HashMap<>();
        for (Person pe : ds.getPersons().values()) {
            if (pe.getPlan() == null) continue;
            for (Tour tr : pe.getPlan().getTours().values()) {
                Purpose p = tr.getMainActivity().getPurpose();
                if (p == Purpose.SUBTOUR || tr.getTourMode() == null) continue;
                c.computeIfAbsent(p, k -> new EnumMap<>(Mode.class)).computeIfAbsent(tr.getTourMode(), k -> new double[1])[0]++;
                tot.computeIfAbsent(p, k -> new int[1])[0]++;
            }
        }
        Map<Purpose, Map<Mode, Double>> out = new HashMap<>();
        for (Purpose p : c.keySet()) {
            Map<Mode, Double> mm = new EnumMap<>(Mode.class);
            for (Mode m : c.get(p).keySet()) mm.put(m, c.get(p).get(m)[0] / tot.get(p)[0]);
            out.put(p, mm);
        }
        return out;
    }

    private static Map<Mode, Double> sharesAll(DataSet ds) {
        Map<Mode, Double> c = new EnumMap<>(Mode.class);
        int tot = 0;
        for (Person pe : ds.getPersons().values()) {
            if (pe.getPlan() == null) continue;
            for (Tour tr : pe.getPlan().getTours().values()) {
                if (tr.getMainActivity().getPurpose() == Purpose.SUBTOUR || tr.getTourMode() == null) continue;
                c.merge(tr.getTourMode(), 1.0, Double::sum);
                tot++;
            }
        }
        for (Mode m : c.keySet()) c.put(m, c.get(m) / tot);
        return c;
    }
}
