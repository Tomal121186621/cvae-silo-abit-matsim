package abm.models.modeChoice;

import abm.data.DataSet;
import abm.data.geo.*;
import abm.data.plans.Mode;
import abm.data.plans.Plan;
import abm.data.plans.Purpose;
import abm.data.pop.Household;
import abm.data.pop.Job;
import abm.data.pop.Person;
import abm.data.pop.Relationship;
import abm.data.travelInformation.TravelTimes;
import abm.models.activityGeneration.frequency.FrequencyGeneratorModel;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.util.MitoUtil;
import junitx.framework.Assert;
import org.junit.Test;

import java.util.Map;

public class HabitualModeChoiceTest {

    @Test
    public void test() {

        AbitResources.initializeResources("C:/models/abit/abit.properties");
        MitoUtil.initializeRandomNumber(AbitUtils.getRandomObject());

        DataSet dataSet = new DataSet();
        final Zone dummyZone = new Zone(1);
        dummyZone.setRegioStaR2Type(RegioStaR2.RURAL);
        dummyZone.setRegioStaRGem5Type(RegioStaRGem5.PROVINCIAL_RURAL);
        dummyZone.setRegioStaR7Type(RegioStaR7.RURAL_PROVICIAL);
        dataSet.getZones().put(1, dummyZone);

        Job dummyJob = new Job(1, 1, "type", dummyZone, 8*60, 8 * 60);

        TravelTimes dummyTravelTimes = new TravelTimes() {
            @Override
            public int getTravelTimeInMinutes(Location origin, Location destination, Mode mode, double time) {
                if (mode == Mode.CAR_DRIVER){
                    return 10;
                } else {
                    return 45;
                }
            }
        };

        dataSet.setTravelTimes(dummyTravelTimes);

        Household household = new Household(1, dummyZone, 1);

        Person person = new Person(1, household, 50, Gender.MALE,
                Relationship.married, Occupation.EMPLOYED, true, dummyJob, 2000,
                480, 480, 2000, null, Disability.WITHOUT);
        household.getPersons().add(person);

        Plan.initializePlan(person);

        final NestedLogitHabitualModeChoiceModel nestedLogitHabitualModeChoiceModel = new NestedLogitHabitualModeChoiceModel(dataSet);
        nestedLogitHabitualModeChoiceModel.chooseHabitualMode(person);
        System.out.println(person.getHabitualMode());

    }

}
