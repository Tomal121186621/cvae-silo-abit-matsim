package abm.matsim;

import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import org.matsim.api.core.v01.Scenario;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.config.groups.PlansCalcRouteConfigGroup;
import org.matsim.core.controler.Controler;
import org.matsim.core.scenario.ScenarioUtils;

/**
 * Runs MATSim with the config created in CreateConfig.java and one of the plan files produced by Abit
 */
public class RunMATSim {

    public static void main(String[] args) {

        AbitResources.initializeResources(args[0]);

        Config config = ConfigUtils.loadConfig("./configBase.xml");
        config.controler().setOutputDirectory("./output/" + AbitResources.instance.getString("run.id")  + "/matsim/");

        config.plans().setInputFile("./output/" + AbitResources.instance.getString("run.id")  + "/matsimPlan_tuesday.xml");

        //for some reason this was not stored in the config created by CreateConfig.java

/*       PlansCalcRouteConfigGroup.TeleportedModeParams carPassengerParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("car_passenger");
        carPassengerParams.setTeleportedModeFreespeedFactor(1.0);
        config.plansCalcRoute().addTeleportedModeParams(carPassengerParams);*/

 /*       {
            PlansCalcRouteConfigGroup.TeleportedModeParams ptParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("train");
            ptParams.setBeelineDistanceFactor(1.5);
            ptParams.setTeleportedModeSpeed(50 / 3.6);
            config.plansCalcRoute().addTeleportedModeParams(ptParams);
        }

        {
            PlansCalcRouteConfigGroup.TeleportedModeParams ptParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("tram_metro");
            ptParams.setBeelineDistanceFactor(1.5);
            ptParams.setTeleportedModeSpeed(30 / 3.6);
            config.plansCalcRoute().addTeleportedModeParams(ptParams);
        }

        {
            PlansCalcRouteConfigGroup.TeleportedModeParams ptParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("bus");
            ptParams.setBeelineDistanceFactor(1.5);
            ptParams.setTeleportedModeSpeed(15 / 3.6);
            config.plansCalcRoute().addTeleportedModeParams(ptParams);
        }

        PlansCalcRouteConfigGroup.TeleportedModeParams bicycleParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("bike");
        bicycleParams.setBeelineDistanceFactor(1.3);
        bicycleParams.setTeleportedModeSpeed(15 / 3.6);
        config.plansCalcRoute().addTeleportedModeParams(bicycleParams);

        PlansCalcRouteConfigGroup.TeleportedModeParams walkParams = new PlansCalcRouteConfigGroup.TeleportedModeParams("walk");
        walkParams.setBeelineDistanceFactor(1.3);
        walkParams.setTeleportedModeSpeed(5 / 3.6);
        config.plansCalcRoute().addTeleportedModeParams(walkParams);*/


        Scenario scenario = ScenarioUtils.createScenario(config);
        ScenarioUtils.loadScenario(scenario);
        Controler controler = new Controler(scenario);
        controler.run();



    }
}
