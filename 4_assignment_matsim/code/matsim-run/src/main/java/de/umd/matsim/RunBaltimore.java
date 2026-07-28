package de.umd.matsim;

import org.matsim.api.core.v01.Scenario;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.config.groups.*;
import org.matsim.core.controler.Controler;
import org.matsim.core.controler.OutputDirectoryHierarchy.OverwriteFileSetting;
import org.matsim.core.scenario.ScenarioUtils;

import java.util.List;
import java.util.Set;

/**
 * Standalone MATSim 2024 traffic assignment for the Baltimore (BMR) study area.
 *
 * Demand = the calibrated MITO trips (modes FIXED from MITO's Apollo mode choice — MATSim assigns
 * routes/times only, it does NOT re-choose modes). Car loads the road network; pt is routed on the
 * pt2matsim-mapped GTFS schedule; ride/walk/bike are teleported. flowCapFactor/storageCapFactor match
 * the 10% sub-sample. The config is built in code to stay robust across MATSim versions.
 *
 * Usage: RunBaltimore <network> <plans> <schedule> <vehicles> <outDir> <iterations> <flowCapFactor>
 */
public class RunBaltimore {

    public static void main(String[] args) {
        String network   = args[0];
        String plans      = args[1];
        String schedule   = args[2];
        String vehicles   = args[3];
        String outDir     = args[4];
        int iterations    = Integer.parseInt(args[5]);
        double flowCap    = Double.parseDouble(args[6]);
        // storageCapFactor: raise above flowCap to avoid spurious spillback gridlock at low sample rates
        // (long inflow/outflow trips occupy link storage). Optional arg[7]; default 0.5.
        double storageCap = args.length > 7 ? Double.parseDouble(args[7]) : 0.5;

        Config config = ConfigUtils.createConfig();
        config.global().setCoordinateSystem("EPSG:26985");
        config.global().setNumberOfThreads(8);

        config.network().setInputFile(network);
        config.plans().setInputFile(plans);

        // --- transit (pt routed on the mapped schedule) ---
        config.transit().setUseTransit(true);
        config.transit().setTransitScheduleFile(schedule);
        config.transit().setVehiclesFile(vehicles);
        config.transit().setTransitModes(Set.of("pt"));
        // widen the stop-search radius: the default 1000 m makes ~65% of pt trips (esp. long/suburban)
        // find no nearby stop and fall back to a teleported walk. 4 km recovers most reachable pt trips.
        config.transitRouter().setSearchRadius(4000.0);
        config.transitRouter().setExtensionRadius(2000.0);

        // --- controller ---
        config.controller().setOutputDirectory(outDir);
        config.controller().setFirstIteration(0);
        config.controller().setLastIteration(iterations);
        config.controller().setOverwriteFileSetting(OverwriteFileSetting.deleteDirectoryIfExists);
        config.controller().setWriteEventsInterval(iterations);   // events at the last iteration
        config.controller().setWritePlansInterval(iterations);
        config.controller().setMobsim("qsim");

        // --- link volumes for AADT/TMAS validation: write linkStats periodically + at the end,
        //     averaged over the last few iterations so the reported volumes are equilibrium volumes ---
        int linkStatsInterval = Math.max(1, iterations / 8);      // ~8 dumps; final one lands at 'iterations'
        config.linkStats().setWriteLinkStatsInterval(linkStatsInterval);
        config.linkStats().setAverageLinkStatsOverIterations(Math.min(5, linkStatsInterval));

        // --- qsim (scaled to the 10% sample) ---
        config.qsim().setFlowCapFactor(flowCap);
        config.qsim().setStorageCapFactor(storageCap);             // tunable; higher avoids spurious spillback gridlock
        config.qsim().setStartTime(0);
        config.qsim().setEndTime(36 * 3600);                       // 36h: let legitimately-late evening tours complete
        config.qsim().setNumberOfThreads(8);
        config.qsim().setMainModes(List.of("car"));
        config.qsim().setVehiclesSource(QSimConfigGroup.VehiclesSource.defaultVehicle);
        config.qsim().setInsertingWaitingVehiclesBeforeDrivingVehicles(true);
        // stuckTime: at 120s ~7% of vehicles were aborted at peak-hour queues (flow-limited, not storage),
        // dropping their downstream link volume and distorting AADT. Raise to 600s so legitimately-queued
        // vehicles clear naturally; only genuine deadlocks (rare with storageCap>=0.40) are removed.
        config.qsim().setStuckTime(600.0);
        config.qsim().setRemoveStuckVehicles(true);

        // --- routing: car on network; ride/walk/bike teleported; pt via transit router ---
        config.routing().setNetworkModes(List.of("car"));
        config.routing().removeModeRoutingParams("ride");
        config.routing().removeModeRoutingParams("walk");
        config.routing().removeModeRoutingParams("bike");
        addTeleport(config, "ride", 1.3, 12.0);   // ~43 km/h beeline (shares roads, congested-ish)
        addTeleport(config, "walk", 1.3, 1.23);   // ~4.4 km/h
        addTeleport(config, "bike", 1.3, 3.1);    // ~11 km/h

        // --- scoring: activity types + mode params ---
        addAct(config, "home", 12*3600);
        addAct(config, "work", 8*3600);
        addAct(config, "education", 6*3600);
        addAct(config, "shopping", 2*3600);
        addAct(config, "other", 2*3600);
        // tour-based stop activity types (intermediate stops)
        addAct(config, "escort", (int)(0.25*3600));
        addAct(config, "eat",    (int)(0.75*3600));
        addAct(config, "errand", (int)(0.50*3600));
        addAct(config, "socialrec", (int)(1.5*3600));
        for (String m : new String[]{"car","pt","ride","walk","bike"}) {
            ScoringConfigGroup.ModeParams mp = new ScoringConfigGroup.ModeParams(m);
            config.scoring().addModeParams(mp);
        }

        // --- replanning: route + departure-time choice only (modes FIXED — mode choice is upstream in ABIT) ---
        ReplanningConfigGroup strat = config.replanning();
        strat.setMaxAgentPlanMemorySize(5);
        strat.setFractionOfIterationsToDisableInnovation(0.8);
        // Explicitly disable the innovative strategies after ~0.8x lastIteration so the last ~20% of
        // iterations only re-select among the settled plan set (routes/times stop mutating -> the run
        // converges to equilibrium volumes). ChangeExpBeta is a selector, not innovation -> stays on.
        int disableInnovationAfter = (int) Math.round(0.8 * iterations);
        addStrategy(config, "ReRoute", 0.15, disableInnovationAfter);
        addStrategy(config, "TimeAllocationMutator", 0.10, disableInnovationAfter);
        addStrategy(config, "ChangeExpBeta", 0.75, -1);   // selector over the evolving choice set (never disabled)
        // departure-time mutation range for the TimeAllocationMutator (±30 min)
        config.timeAllocationMutator().setMutationRange(1800.0);
        config.timeAllocationMutator().setAffectingDuration(false);

        Scenario scenario = ScenarioUtils.loadScenario(config);
        Controler controler = new Controler(scenario);
        controler.run();
    }

    private static void addAct(Config c, String type, double dur) {
        ScoringConfigGroup.ActivityParams a = new ScoringConfigGroup.ActivityParams(type);
        a.setTypicalDuration(dur);
        c.scoring().addActivityParams(a);
    }
    private static void addTeleport(Config c, String mode, double beeline, double speed) {
        RoutingConfigGroup.TeleportedModeParams t = new RoutingConfigGroup.TeleportedModeParams(mode);
        t.setBeelineDistanceFactor(beeline);
        t.setTeleportedModeSpeed(speed);
        c.routing().addTeleportedModeParams(t);
    }
    private static void addStrategy(Config c, String name, double weight) {
        addStrategy(c, name, weight, -1);
    }
    private static void addStrategy(Config c, String name, double weight, int disableAfterIteration) {
        ReplanningConfigGroup.StrategySettings ss = new ReplanningConfigGroup.StrategySettings();
        ss.setStrategyName(name);
        ss.setWeight(weight);
        if (disableAfterIteration >= 0) ss.setDisableAfter(disableAfterIteration);
        c.replanning().addStrategySettings(ss);
    }
}
