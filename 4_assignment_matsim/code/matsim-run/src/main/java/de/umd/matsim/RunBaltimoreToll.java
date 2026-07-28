package de.umd.matsim;

import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.TransportMode;
import org.matsim.api.core.v01.population.Person;
import org.matsim.contrib.roadpricing.RoadPricingConfigGroup;
import org.matsim.contrib.roadpricing.RoadPricingModule;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.config.groups.*;
import org.matsim.core.controler.AbstractModule;
import org.matsim.core.controler.Controler;
import org.matsim.core.controler.OutputDirectoryHierarchy.OverwriteFileSetting;
import org.matsim.core.population.PersonUtils;
import org.matsim.core.scenario.ScenarioUtils;

import java.util.List;
import java.util.Set;

/**
 * I-695 congestion-pricing MATSim runner (Phase 1 = toll-capable base).
 *
 * Extends the validated RunBaltimore assignment with an INNER-LOOP mode-choice response so a road-pricing
 * toll can shift mode / route / departure time with NO outer loop (MATSim-NYC recipe, paper Sec. 5):
 *
 *   1. The Maryland MNL mode-choice model is ported into the MATSim scorer per MODE_SCORER_MAPPING.md
 *      (per-mode ASC + travel-time coef + monetaryDistanceRate; car travel-time NORMALIZED to 0 and the
 *      time cost carried by marginalUtilityOfPerforming = 0.78/h; single car-anchored
 *      marginalUtilityOfMoney = 0.026 utils/$ so the toll is scored car-consistently).
 *   2. SubtourModeChoice (+ ReRoute + TimeAllocationMutator + ChangeExpBeta) lets residents re-choose.
 *      Car availability is honoured from the population's `autos`/`driversLicense` attributes.
 *   3. RoadPricing (org.matsim.contrib.roadpricing) adds the I-695 toll as monetary disutility when a
 *      toll file is supplied. With tollFile = NONE (Phase-1 base) no toll is applied — the run is the
 *      gate that must reproduce the validated base mode shares once the ASCs are re-anchored.
 *
 * The five mode ASCs are overridable at launch (-Dasc.car/-Dasc.pt/-Dasc.ride/-Dasc.walk/-Dasc.bike)
 * so the base can be re-anchored across short calibration passes (ASC += ln(target/sim)) WITHOUT
 * recompiling; car is the reference and stays 0. Everything else matches the validated base config
 * (flowCap 0.10, storageCap 0.13, stuckTime 120, removeStuckVehicles, endTime 36h).
 *
 * Usage: RunBaltimoreToll <network> <plans> <schedule> <vehicles> <outDir> <iterations> <flowCap>
 *                         [storageCap] [tollFile|NONE]
 */
public class RunBaltimoreToll {

    public static void main(String[] args) {
        String network    = args[0];
        String plans       = args[1];
        String schedule    = args[2];
        String vehicles    = args[3];
        String outDir      = args[4];
        int iterations     = Integer.parseInt(args[5]);
        double flowCap     = Double.parseDouble(args[6]);
        double storageCap  = args.length > 7 ? Double.parseDouble(args[7]) : 0.5;
        String tollFile    = args.length > 8 ? args[8] : "NONE";

        // --- re-anchorable mode ASCs (Sec. 3 pre-anchor starting values; car frozen at 0 reference) ---
        double ascCar  = Double.parseDouble(System.getProperty("asc.car",  "0.00"));
        double ascPt   = Double.parseDouble(System.getProperty("asc.pt",   "2.25"));
        double ascRide = Double.parseDouble(System.getProperty("asc.ride", "3.87"));
        double ascWalk = Double.parseDouble(System.getProperty("asc.walk", "3.97"));
        double ascBike = Double.parseDouble(System.getProperty("asc.bike", "-0.20"));

        int nThreads = Integer.parseInt(System.getProperty("threads", "8"));
        Config config = ConfigUtils.createConfig();
        config.global().setCoordinateSystem("EPSG:26985");
        config.global().setNumberOfThreads(nThreads);

        config.network().setInputFile(network);
        config.plans().setInputFile(plans);

        // --- transit (pt routed on the mapped schedule) ---
        config.transit().setUseTransit(true);
        config.transit().setTransitScheduleFile(schedule);
        config.transit().setVehiclesFile(vehicles);
        config.transit().setTransitModes(Set.of("pt"));
        config.transitRouter().setSearchRadius(4000.0);
        config.transitRouter().setExtensionRadius(2000.0);

        // --- controller ---
        config.controller().setOutputDirectory(outDir);
        config.controller().setFirstIteration(0);
        config.controller().setLastIteration(iterations);
        config.controller().setOverwriteFileSetting(OverwriteFileSetting.deleteDirectoryIfExists);
        config.controller().setMobsim("qsim");
        // Disk-light calibration: the subsample re-anchor passes only need modestats.csv (written every
        // iteration at the output root regardless), so suppress the big per-iteration writes (events,
        // plans, snapshots, linkStats) and the end-of-run dump. The FINAL frozen-ASC base run sets
        // -Dwrite.outputs=true to restore full outputs for validation.
        boolean writeOutputs = Boolean.parseBoolean(System.getProperty("write.outputs", "true"));
        if (writeOutputs) {
            config.controller().setWriteEventsInterval(iterations);
            config.controller().setWritePlansInterval(iterations);
            int linkStatsInterval = Math.max(1, iterations / 8);
            config.linkStats().setWriteLinkStatsInterval(linkStatsInterval);
            config.linkStats().setAverageLinkStatsOverIterations(Math.min(5, linkStatsInterval));
        } else {
            // disk-light calibration: no per-iteration events/plans/snapshots/linkStats, BUT keep the
            // end-of-run dump ON so output_plans.xml.gz is written (small on the subsample) for
            // warm-starting the next pass. (~15-25 MB; cleaned between passes.)
            config.controller().setWriteEventsInterval(0);
            config.controller().setWritePlansInterval(0);
            config.controller().setWriteSnapshotsInterval(0);
            config.controller().setDumpDataAtEnd(true);
            config.linkStats().setWriteLinkStatsInterval(0);
        }

        // --- qsim (scaled to the 10% sample) ---
        config.qsim().setFlowCapFactor(flowCap);
        config.qsim().setStorageCapFactor(storageCap);
        config.qsim().setStartTime(0);
        config.qsim().setEndTime(36 * 3600);
        config.qsim().setNumberOfThreads(nThreads);
        config.qsim().setMainModes(List.of("car"));
        config.qsim().setVehiclesSource(QSimConfigGroup.VehiclesSource.defaultVehicle);
        config.qsim().setInsertingWaitingVehiclesBeforeDrivingVehicles(true);
        config.qsim().setStuckTime(120.0);
        config.qsim().setRemoveStuckVehicles(true);

        // --- routing: car AND ride on the network; walk/bike teleported; pt via transit router ---
        // ride (car-passenger) is ROUTED ON THE CAR NETWORK so it experiences the SAME congested travel
        // times as car (its travel-time binding -> car's TravelTime, set on the Controler below). It is
        // NOT a qsim mainMode, so it is teleported over its network-route time and adds no extra traffic.
        // Previously ride was teleported at a fixed 43 km/h free-flow speed, which gave it an artificial
        // speed advantage over congested car -> ride became a mode-choice sink AND could not respond to
        // the toll's congestion/diversion in Phase 2. Routing on the network fixes both.
        config.routing().setNetworkModes(List.of("car", "ride"));
        config.routing().removeModeRoutingParams("ride");
        config.routing().removeModeRoutingParams("walk");
        config.routing().removeModeRoutingParams("bike");
        addTeleport(config, "walk", 1.3, 1.23);
        addTeleport(config, "bike", 1.3, 3.1);

        // --- scoring: activity types ---
        addAct(config, "home", 12*3600);
        addAct(config, "work", 8*3600);
        addAct(config, "education", 6*3600);
        addAct(config, "shopping", 2*3600);
        addAct(config, "other", 2*3600);
        addAct(config, "escort", (int)(0.25*3600));
        addAct(config, "eat",    (int)(0.75*3600));
        addAct(config, "errand", (int)(0.50*3600));
        addAct(config, "socialrec", (int)(1.5*3600));

        // --- scoring: mode params ported from the MD MNL model (MODE_SCORER_MAPPING.md Sec. 3) ---
        // Global: car-anchored money utility + performing carries the (normalized-away) car time cost.
        config.scoring().setMarginalUtlOfWaiting_utils_hr(0.0);
        config.scoring().setPerforming_utils_hr(0.78);
        // base (median-person) money utility anchored to Lin, Spissu & Cirillo (2024, TR-A 182):
        // pre-pandemic Express Lanes WTP $26-28/h -> $27/h in early-2020 dollars, expressed in
        // NOMINAL 2023 DOLLARS (CPI 2020->2023 ~ +17.8%) for unit consistency with the 2023 toll
        // rates: $31.8/h -> 0.78/31.8 = 0.0245 utils/$. Sensitivities: $27 (unadjusted), $36 (pandemic).
        config.scoring().setMarginalUtilityOfMoney(0.0245);
        // car: reference. travel-time coef normalized to 0; time cost = -performing. fuel ~$0.075/km.
        addMode(config, "car",  ascCar,   0.00, 0.0,       -0.000075);
        // pt: BUS-based, normalized (-1.80 + 0.78 = -1.02/h). fare $0.50/km.
        addMode(config, "pt",   ascPt,   -1.02, 0.0,       -0.0005);
        // ride: passenger time valued AS CAR TIME (performing channel only), matching ABIT's GC where
        // passenger time enters identically to driver time (VOT divides only the money term). The
        // earlier -1.11/h blend (bus-like published tables) made ride's time disutility 2.4x car's,
        // which under full-scale congestion crushed the switchable margin (measured: ride response to
        // ASC ~17x weaker than logit) and would have multiplied any scenario's congestion change into
        // ride share artifacts. (2026-07-13, full-scale calibration finding.)
        addMode(config, "ride", ascRide,  0.00, 0.0,       -0.000075);
        // walk/bike: the source model penalizes these by tripLength (WALK -1.17/km, BIKE -0.28/km) with
        // NO time term. The original port put that on marginalUtilityOfDistance, but MATSim does not
        // effectively score distance on TELEPORTED legs (observed: avg walk trip ran to ~5.5 km with
        // walk person-hours EXCEEDING car's, and walk share was a growing attractor) -- so with net time
        // = +0.78-0.78 = 0, walk/bike were essentially free and over-chosen regardless of ASC. Fix:
        // convert the per-km penalty into the equivalent per-HOUR time disutility via the teleport speed
        // (walk 1.23 m/s = 4.43 km/h; bike 3.1 m/s = 11.16 km/h), which lands in the reliably-scored time
        // channel and is per-trip-equivalent to a working distance penalty:
        //   walk net -1.17/km * 4.43 km/h = -5.18/h  -> marginalUtilityOfTraveling = -5.18 + 0.78 = -4.40
        //   bike net -0.28/km * 11.16 km/h = -3.13/h -> marginalUtilityOfTraveling = -3.13 + 0.78 = -2.345
        addMode(config, "walk", ascWalk, -4.40,  0.0,  0.0);
        addMode(config, "bike", ascBike, -2.345, 0.0,  0.0);

        // --- replanning: inner-loop mode choice ON (residents may switch) ---
        // Plan-memory cap: with 3 innovation strategies each agent accumulates plans; on the full 280k
        // population this overflowed -Xmx13g (18 GB machine) and hung at ~it.11's mobsim start. Keep it
        // small (override with -Dplan.memory; 3 for the full-pop base, 5 is fine on subsamples).
        int planMemory = Integer.parseInt(System.getProperty("plan.memory", "5"));
        ReplanningConfigGroup strat = config.replanning();
        strat.setMaxAgentPlanMemorySize(planMemory);
        // 0.8 collapses mode shares in the last 20% (selection drains to best plan once SubtourModeChoice
        // stops injecting alternatives); calibrate and run pricing with -Dinnovoff=1.0 so the reported
        // shares are the innovation-on stationary equilibrium and toll-induced mode shifts stay possible.
        strat.setFractionOfIterationsToDisableInnovation(
                Double.parseDouble(System.getProperty("innovoff", "0.8")));

        // HYBRID design: mode choice is done by ABIT in the OUTER loop (price-elastic, on tolled skims);
        // MATSim's INNER loop only does route + departure-time (modes FIXED from the input plans). So
        // SubtourModeChoice is OFF by default. Set -Dmodechoice=true to re-enable the inner-loop mode
        // choice (legacy scorer-calibration path).
        boolean innerModeChoice = Boolean.parseBoolean(System.getProperty("modechoice", "false"));
        if (innerModeChoice) {
            // SMC's uniform random injection puts a standing churn floor under every mode
            // (~weight-proportional); pt/bike targets sit below the floor at 0.15, so the
            // calibrated runs use -Dsmc.weight=0.04 (slack goes to ChangeExpBeta selection).
            double smcWeight = Double.parseDouble(System.getProperty("smc.weight", "0.15"));
            addStrategy(config, "SubtourModeChoice", smcWeight);
            addStrategy(config, "ReRoute", 0.15);
            addStrategy(config, "TimeAllocationMutator", 0.10);
            addStrategy(config, "ChangeExpBeta", 0.75 - smcWeight);
            config.subtourModeChoice().setModes(new String[]{"car","pt","ride","walk","bike"});
            config.subtourModeChoice().setChainBasedModes(new String[]{});
            config.subtourModeChoice().setConsiderCarAvailability(true);
            config.subtourModeChoice().setBehavior(
                    org.matsim.core.replanning.modules.SubtourModeChoice.Behavior.betweenAllAndFewerConstraints);
        } else {
            // fixed modes: route + departure-time inner loop only (weights sum to 1.0 without SMC)
            addStrategy(config, "ReRoute", 0.15);
            addStrategy(config, "TimeAllocationMutator", 0.10);
            addStrategy(config, "ChangeExpBeta", 0.75);
        }
        config.timeAllocationMutator().setMutationRange(1800.0);
        config.timeAllocationMutator().setAffectingDuration(false);

        // --- optional road pricing (Phase-1 base runs with tollFile = NONE) ---
        boolean toll = tollFile != null && !tollFile.isEmpty() && !tollFile.equalsIgnoreCase("NONE");
        if (toll) {
            RoadPricingConfigGroup rp = ConfigUtils.addOrGetModule(config, RoadPricingConfigGroup.class);
            rp.setTollLinksFile(tollFile);
        }

        Scenario scenario = ScenarioUtils.loadScenario(config);

        // ride is now routed on the network, but the links are annotated only with mode "car", so the
        // "ride" sub-network would be empty (nof_nodes=0) and routing would fail. Allow "ride" on every
        // car link so ride shares the car network (and thus its congested travel times).
        int rideLinks = 0;
        for (org.matsim.api.core.v01.network.Link link : scenario.getNetwork().getLinks().values()) {
            Set<String> modes = link.getAllowedModes();
            if (modes.contains("car") && !modes.contains("ride")) {
                Set<String> nm = new java.util.HashSet<>(modes);
                nm.add("ride");
                link.setAllowedModes(nm);
                rideLinks++;
            }
        }
        System.out.println("[RunBaltimoreToll] added mode 'ride' to " + rideLinks + " car links");

        // Set MATSim carAvail ("always"/"never") for SubtourModeChoice's considerCarAvailability.
        // PRIMARY: seed from ABIT's assigned mode -- any agent whose ABIT plan has a "car" (CAR_DRIVER)
        // leg demonstrably HAD a car for that trip, so carAvail=always. This guarantees MATSim can
        // reproduce ABIT's ~77% car-driver share and removes an artificial ceiling (the household
        // autos+license attributes marked ~4.7% of ABIT car-drivers as carless, e.g. autos=0 rounding or
        // a licensed 2nd driver in a 0-car record). FALLBACK for agents with no car leg: autos>0 & license.
        int carless = 0, seededByMode = 0;
        for (Person p : scenario.getPopulation().getPersons().values()) {
            boolean hadCarLeg = false;
            if (p.getSelectedPlan() != null) {
                for (org.matsim.api.core.v01.population.PlanElement pe : p.getSelectedPlan().getPlanElements()) {
                    if (pe instanceof org.matsim.api.core.v01.population.Leg
                            && "car".equals(((org.matsim.api.core.v01.population.Leg) pe).getMode())) {
                        hadCarLeg = true; break;
                    }
                }
            }
            Object autosAttr   = p.getAttributes().getAttribute("autos");
            Object licenseAttr = p.getAttributes().getAttribute("driversLicense");
            int autos = (autosAttr instanceof Number) ? ((Number) autosAttr).intValue()
                        : (autosAttr != null ? parseIntSafe(autosAttr.toString()) : 1);
            boolean licensed = licenseAttr == null || Boolean.parseBoolean(licenseAttr.toString());
            boolean carAvail = hadCarLeg || (autos > 0 && licensed);
            if (carAvail && !(autos > 0 && licensed)) seededByMode++;   // recovered by the ABIT-mode seed
            PersonUtils.setCarAvail(p, carAvail ? "always" : "never");
            if (!carAvail) carless++;
        }
        int nPop = scenario.getPopulation().getPersons().size();
        System.out.println("[RunBaltimoreToll] carAvail=never for " + carless + " / " + nPop
                + " residents (" + String.format("%.1f", 100.0 * (nPop - carless) / nPop)
                + "% always; " + seededByMode + " recovered by ABIT-mode seed)");
        System.out.println("[RunBaltimoreToll] ASCs  car=" + ascCar + " pt=" + ascPt + " ride=" + ascRide
                + " walk=" + ascWalk + " bike=" + ascBike + "  toll=" + (toll ? tollFile : "NONE"));

        // walk/bike max-distance cutoff for SubtourModeChoice (curing the non-motorized floor): walk
        // dropped from the choice set when the agent's longest trip > walk.maxdist, bike > bike.maxdist.
        final double walkMaxDist = Double.parseDouble(System.getProperty("walk.maxdist", "2000"));
        final double bikeMaxDist = Double.parseDouble(System.getProperty("bike.maxdist", "5000"));
        final String[] scModes = {"car", "pt", "ride", "walk", "bike"};
        System.out.println("[RunBaltimoreToll] walk.maxdist=" + walkMaxDist + "m  bike.maxdist=" + bikeMaxDist + "m");

        // --- INCOME-DEPENDENT MONEY UTILITY (equity response; 2026-07-12) ---
        // marginalUtilityOfMoney(person) = base * (medianIncome / hhIncome)^elasticity, i.e. VOT
        // proportional to income (elasticity 1.0 default; -Dincome.vot.elasticity=0 restores uniform).
        // This is what makes the toll response income-elastic: same $3 = 15 min to a low-income
        // driver at VOT ~$12/h, 3 min at ~$60/h. Joint demographic structure (location, cars,
        // activity patterns) is inherited from SILO/ABIT plans; this adds the cost-sensitivity margin.
        final double votElast = Double.parseDouble(System.getProperty("income.vot.elasticity", "1.0"));
        java.util.List<Double> incs = new java.util.ArrayList<>();
        for (org.matsim.api.core.v01.population.Person p : scenario.getPopulation().getPersons().values()) {
            Object a = p.getAttributes().getAttribute("hhIncome");
            if (a instanceof Number) incs.add(((Number) a).doubleValue());
        }
        java.util.Collections.sort(incs);
        final double medianInc = incs.isEmpty() ? 75000.0 : incs.get(incs.size() / 2);
        System.out.println("[RunBaltimoreToll] income-VOT elasticity=" + votElast
                + "  median hhIncome=" + medianInc + " (n=" + incs.size() + ")");

        Controler controler = new Controler(scenario);
        // ride rides at CAR's congested travel time: bind ride's routing TravelTime to the car network
        // TravelTime (the congestion-aware TravelTimeCalculator output) and reuse car's disutility factory.
        // Also install the distance-constrained PermissibleModesCalculator for SubtourModeChoice.
        final Config cfgF = config;
        controler.addOverridingModule(new AbstractModule() {
            @Override public void install() {
                addTravelTimeBinding(TransportMode.ride).to(networkTravelTime());
                addTravelDisutilityFactoryBinding(TransportMode.ride).to(carTravelDisutilityFactoryKey());
                bind(org.matsim.core.population.algorithms.PermissibleModesCalculator.class)
                        .toInstance(new DistanceConstrainedPermissibleModes(scModes, walkMaxDist, bikeMaxDist));
                if (votElast > 0) {
                    bind(org.matsim.core.scoring.functions.ScoringParametersForPerson.class)
                            .toInstance(new IncomeScoringParams(cfgF, medianInc, votElast));
                }
            }
        });
        if (toll) {
            controler.addOverridingModule(new RoadPricingModule());
        }
        controler.run();
    }

    private static int parseIntSafe(String s) {
        try { return (int) Double.parseDouble(s.trim()); } catch (Exception e) { return 1; }
    }

    /** Person-specific scoring following Bas Vicente & Cirillo (2017, NTC2015-SU-R-09), Jara-Diaz &
     *  Videla (1989) form: V = b1(I-c) + b2(I-c)^2 + ... with I = income PER TRIP
     *  (= hhIncome / (2.88 trips/day x 260 working days), the report's transformation).
     *  Marginal utility of money: lambda(I) = b1 + 2*b2*I, MXL estimates b1=0.525, b2=-0.001
     *  (Fig.1, preferred mixed-logit model, Maryland Capital Beltway SP, n=766).
     *  MATSim's marginalUtilityOfMoney(person) = base * lambda(I_p)/lambda(I_median), so the median
     *  person keeps the base VOT anchor (set from Lin, Spissu & Cirillo 2024, TR-A 182: pre-pandemic
     *  Express Lanes WTP $26-28/h -> $27/h). The quadratic turns negative above the SP sample range
     *  (~$196k/yr hh income), so the RELATIVE factor is clamped (documented tail regularization). */
    static class IncomeScoringParams implements org.matsim.core.scoring.functions.ScoringParametersForPerson {
        static final double B1 = 0.525, TWO_B2 = -0.002;            // MXL (I-C) and 2x(I-C)^2 coefs
        static final double TRIPS_PER_YEAR = 2.88 * 260.0;          // income-per-trip transformation
        // SILO incomes are maintained in 2016 dollars; the coefficients are scaled to the survey's
        // 2011 dollars -> deflate incomes before evaluating lambda (CPI 2011->2016 ~ +6.7%).
        static final double INCOME_2016_TO_2011 = 1.0 / 1.067;
        static final double FACTOR_MIN = 0.4, FACTOR_MAX = 2.5;     // tail clamp = ABIT precedent (VOT_FACTOR_MIN/MAX in MarylandFullModeChoice); 0.25 variant = sensitivity run
        private final Config config;
        private final double medianIncome, elasticity;              // elasticity kept as on/off switch (>0 = on)
        private final java.util.Map<org.matsim.api.core.v01.Id<org.matsim.api.core.v01.population.Person>,
                org.matsim.core.scoring.functions.ScoringParameters> cache = new java.util.concurrent.ConcurrentHashMap<>();
        IncomeScoringParams(Config config, double medianIncome, double elasticity) {
            this.config = config; this.medianIncome = medianIncome; this.elasticity = elasticity;
        }
        private static double lambda(double annualIncome) {
            double perTrip = annualIncome * INCOME_2016_TO_2011 / TRIPS_PER_YEAR;
            return B1 + TWO_B2 * perTrip;
        }
        @Override
        public org.matsim.core.scoring.functions.ScoringParameters getScoringParameters(
                org.matsim.api.core.v01.population.Person person) {
            return cache.computeIfAbsent(person.getId(), id -> {
                double inc = medianIncome;
                Object a = person.getAttributes().getAttribute("hhIncome");
                if (a instanceof Number) inc = ((Number) a).doubleValue();
                else if (a != null) { try { inc = Double.parseDouble(a.toString()); } catch (Exception ignored) {} }
                double factor = lambda(inc) / lambda(medianIncome);
                factor = Math.max(FACTOR_MIN, Math.min(FACTOR_MAX, factor));
                org.matsim.core.scoring.functions.ScoringParameters.Builder b =
                        new org.matsim.core.scoring.functions.ScoringParameters.Builder(
                                config.scoring(), config.scoring().getScoringParameters(null), config.scenario());
                b.setMarginalUtilityOfMoney(config.scoring().getMarginalUtilityOfMoney() * factor);
                return b.build();
            });
        }
    }

    private static void addAct(Config c, String type, double dur) {
        ScoringConfigGroup.ActivityParams a = new ScoringConfigGroup.ActivityParams(type);
        a.setTypicalDuration(dur);
        c.scoring().addActivityParams(a);
    }
    private static void addMode(Config c, String mode, double constant, double travelUtilPerHr,
                                double distUtilPerM, double monetaryDistRate) {
        ScoringConfigGroup.ModeParams mp = new ScoringConfigGroup.ModeParams(mode);
        mp.setConstant(constant);
        mp.setMarginalUtilityOfTraveling(travelUtilPerHr);
        mp.setMarginalUtilityOfDistance(distUtilPerM);
        mp.setMonetaryDistanceRate(monetaryDistRate);
        c.scoring().addModeParams(mp);
    }
    private static void addTeleport(Config c, String mode, double beeline, double speed) {
        RoutingConfigGroup.TeleportedModeParams t = new RoutingConfigGroup.TeleportedModeParams(mode);
        t.setBeelineDistanceFactor(beeline);
        t.setTeleportedModeSpeed(speed);
        c.routing().addTeleportedModeParams(t);
    }
    private static void addStrategy(Config c, String name, double weight) {
        ReplanningConfigGroup.StrategySettings ss = new ReplanningConfigGroup.StrategySettings();
        ss.setStrategyName(name);
        ss.setWeight(weight);
        c.replanning().addStrategySettings(ss);
    }
}
