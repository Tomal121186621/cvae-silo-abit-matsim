package abm.matsim;

import abm.properties.AbitResources;
import de.tum.bgu.msm.data.Mode;
import de.tum.bgu.msm.resources.Properties;
import de.tum.bgu.msm.resources.Resources;
import org.matsim.api.core.v01.TransportMode;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigGroup;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.config.ConfigWriter;
import org.matsim.core.config.groups.PlanCalcScoreConfigGroup;
import org.matsim.core.config.groups.PlansCalcRouteConfigGroup;
import org.matsim.core.config.groups.StrategyConfigGroup;
import org.matsim.core.controler.OutputDirectoryHierarchy;
import org.matsim.core.replanning.strategies.DefaultPlanStrategiesModule;

import java.util.HashSet;
import java.util.Set;

/**
 * Creates a basic config for MATSim that is compatible wth modes and activity purposes of ABIT.
 * It does not point to the plans file, so this has to be decided in RunMATSim.java
 */
public class ConfigureMATSim {

    public static void main(String[] args) {

        AbitResources.initializeResources(args[0]);

        new ConfigureMATSim().createMatsimConfig();
    }

    void createMatsimConfig() {

        Config config = ConfigUtils.createConfig();

        config.controler().setFirstIteration(0);
        config.controler().setLastIteration(AbitResources.instance.getInt("matsim.iterations"));
        config.controler().setMobsim("qsim");
        config.controler().setWritePlansInterval(config.controler().getLastIteration());
        config.controler().setWriteEventsInterval(config.controler().getLastIteration());

        config.controler().setOverwriteFileSetting(OutputDirectoryHierarchy.OverwriteFileSetting.deleteDirectoryIfExists);


        {
            StrategyConfigGroup.StrategySettings strategySettings = new StrategyConfigGroup.StrategySettings();
            strategySettings.setStrategyName("ChangeExpBeta");
            strategySettings.setWeight(0.8);
            config.strategy().addStrategySettings(strategySettings);
        }
        {
            StrategyConfigGroup.StrategySettings strategySettings = new StrategyConfigGroup.StrategySettings();
            strategySettings.setStrategyName("ReRoute");
            strategySettings.setWeight(0.2);
            config.strategy().addStrategySettings(strategySettings);
        }

//        {
//            config.timeAllocationMutator().setMutationRange(1800);
//            config.timeAllocationMutator().setAffectingDuration(true);
//            StrategyConfigGroup.StrategySettings strategySettings = new StrategyConfigGroup.StrategySettings();
//            strategySettings.setStrategyName(DefaultPlanStrategiesModule.DefaultStrategy.TimeAllocationMutator_ReRoute);
//            strategySettings.setWeight(0.1);
//            config.strategy().addStrategySettings(strategySettings);
//        }

//        StrategyConfigGroup.StrategySettings strategy =
//                new StrategyConfigGroup.StrategySettings();
//        strategy.setStrategyName(
//                DefaultPlanStrategiesModule.DefaultStrategy.ChangeTripMode);
//        strategy.setWeight(0.2);
//        config.changeMode().setModes(new String[]{"car", "bike", "walk", "bus", "tram_metro", "train"});
//        config.strategy().addStrategySettings(strategy);

        config.strategy().setFractionOfIterationsToDisableInnovation(0.7);
        config.strategy().setMaxAgentPlanMemorySize(4);

        PlanCalcScoreConfigGroup.ActivityParams homeActivity = new PlanCalcScoreConfigGroup.ActivityParams("home");
        homeActivity.setTypicalDuration(0.5 * 60 * 60);
        homeActivity.setScoringThisActivityAtAll(false);
        config.planCalcScore().addActivityParams(homeActivity);

        PlanCalcScoreConfigGroup.ActivityParams workActivity = new PlanCalcScoreConfigGroup.ActivityParams("work");
        workActivity.setTypicalDuration(0.5 * 60 * 60);
        config.planCalcScore().addActivityParams(workActivity);

        PlanCalcScoreConfigGroup.ActivityParams educationActivity = new PlanCalcScoreConfigGroup.ActivityParams("education");
        educationActivity.setTypicalDuration(0.5 * 60 * 60);
        config.planCalcScore().addActivityParams(educationActivity);

        PlanCalcScoreConfigGroup.ActivityParams shoppingActivity = new PlanCalcScoreConfigGroup.ActivityParams("shopping");
        shoppingActivity.setTypicalDuration(0.5 * 60 * 60);
        config.planCalcScore().addActivityParams(shoppingActivity);

        PlanCalcScoreConfigGroup.ActivityParams otherActivity = new PlanCalcScoreConfigGroup.ActivityParams("other");
        otherActivity.setTypicalDuration(0.5 * 60 * 60);
        config.planCalcScore().addActivityParams(otherActivity);

        PlanCalcScoreConfigGroup.ActivityParams recreationActivity = new PlanCalcScoreConfigGroup.ActivityParams("recreation");
        recreationActivity.setTypicalDuration(0.5 * 60 * 60);
        config.planCalcScore().addActivityParams(recreationActivity);

        PlanCalcScoreConfigGroup.ActivityParams accompanyActivity = new PlanCalcScoreConfigGroup.ActivityParams("accompany");
        accompanyActivity.setTypicalDuration(0.5 * 60 * 60);
        config.planCalcScore().addActivityParams(accompanyActivity);

        config.plansCalcRoute().setNetworkModes(Set.of(TransportMode.car));



        PlansCalcRouteConfigGroup.TeleportedModeParams carPassengerParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("car_passenger");
        carPassengerParams.setTeleportedModeFreespeedFactor(1.0);
        config.plansCalcRoute().addTeleportedModeParams(carPassengerParams);


        PlansCalcRouteConfigGroup.TeleportedModeParams ptParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("pt");
        ptParams.setBeelineDistanceFactor(1.5);
        ptParams.setTeleportedModeSpeed(50 / 3.6);
        config.plansCalcRoute().addTeleportedModeParams(ptParams);



        PlansCalcRouteConfigGroup.TeleportedModeParams bicycleParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("bike");
        bicycleParams.setBeelineDistanceFactor(1.3);
        bicycleParams.setTeleportedModeSpeed(15 / 3.6);
        config.plansCalcRoute().addTeleportedModeParams(bicycleParams);

        PlansCalcRouteConfigGroup.TeleportedModeParams walkParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("walk");
        walkParams.setBeelineDistanceFactor(1.3);
        walkParams.setTeleportedModeSpeed(5 / 3.6);
        config.plansCalcRoute().addTeleportedModeParams(walkParams);


/*        {
            PlanCalcScoreConfigGroup.ModeParams modeParams
                    = config.planCalcScore().getOrCreateModeParams("bus");
            config.planCalcScore().addModeParams(modeParams);
        }


        {
            PlanCalcScoreConfigGroup.ModeParams modeParams
                    = config.planCalcScore().getOrCreateModeParams("tram_metro");
            config.planCalcScore().addModeParams(modeParams);
        }

        {
            PlanCalcScoreConfigGroup.ModeParams modeParams
                    = config.planCalcScore().getOrCreateModeParams("train");
            config.planCalcScore().addModeParams(modeParams);
        }*/


        String runId = "abit";
        config.controler().setRunId(runId);
        config.network().setInputFile(AbitResources.instance.getString("matsim.network"));
        config.global().setCoordinateSystem("EPSG:31468");

        config.qsim().setNumberOfThreads(16);
        config.qsim().setEndTime(30 * 60 * 60);
        config.global().setNumberOfThreads(16);
        config.parallelEventHandling().setNumberOfThreads(16);

        double abitScaleFactor = AbitResources.instance.getDouble("scale.factor", 1.0);
        double matsimScaleFactor = AbitResources.instance.getDouble("matsim.scale.factor", 1.0);
        config.qsim().setFlowCapFactor(Math.max(abitScaleFactor * matsimScaleFactor, 0.01));
        config.qsim().setStorageCapFactor(Math.max(abitScaleFactor * matsimScaleFactor, 0.01));



        config.transit().setUseTransit(false);
//        config.transit().setTransitScheduleFile(AbitResources.instance.getString("matsim.pt.schedule"));
//        config.transit().setVehiclesFile(AbitResources.instance.getString("matsim.pt.vehicles"));
//        config.transit().setTransitModes(Set.of("train", "bus", "tram_metro"));
//        config.transit().setUsingTransitInMobsim(false);

        new ConfigWriter(config).write("./configBase.xml");
        ConfigUtils.writeMinimalConfig(config, "./configMinimal.xml");
        ConfigUtils.writeConfig(config, "./config_configUtil.xml");


        //ConfigUtils.writeConfig(config, "./configBase.xml");

    }
}
