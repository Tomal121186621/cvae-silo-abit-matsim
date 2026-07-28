package abm;

import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.Population;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.controler.Controler;
import org.matsim.core.population.PopulationUtils;
import org.matsim.core.scenario.ScenarioUtils;

import java.util.Iterator;

public class RunMatsim {
    public static void main(String[] args) {


    Config config = ConfigUtils.loadConfig("C:\\models\\abit_standalone\\configBaseAbit.xml");

    // Set network, plans, vehicles
        config.network().setInputFile("C:\\models\\MITO\\mitoMunich\\input\\trafficAssignment\\pt\\network_pt_road.xml.gz");
        config.plans().setInputFile("C:\\models\\abit_standalone\\output\\updatedStartTimeDurationDistributions2\\matsimPlan_friday.xml");

    // Set scale factor
    double scaleFactor = 0.01;
        config.qsim().setFlowCapFactor(scaleFactor);
        config.qsim().setStorageCapFactor(scaleFactor);

    Scenario scenario = ScenarioUtils.loadScenario(config);
    Controler controler = new Controler(scenario);


       /* // define strategies:
        {
            StrategyConfigGroup.StrategySettings strat = new StrategyConfigGroup.StrategySettings();
            strat.setStrategyName(DefaultPlanStrategiesModule.DefaultStrategy.ReRoute);
            strat.setWeight(0.15);
            config.strategy().addStrategySettings(strat);
        }
        {
            StrategyConfigGroup.StrategySettings strat = new StrategyConfigGroup.StrategySettings();
            strat.setStrategyName(DefaultPlanStrategiesModule.DefaultSelector.ChangeExpBeta);
            strat.setWeight(0.9);
            config.strategy().addStrategySettings(strat);
        }
        config.strategy().setMaxAgentPlanMemorySize(5);
        config.strategy().setFractionOfIterationsToDisableInnovation(0.9);
*/
        config.controler().setLastIteration(200);
        config.global().setNumberOfThreads(16);
        config.qsim().setNumberOfThreads(8);

        controler.run();
}
}
