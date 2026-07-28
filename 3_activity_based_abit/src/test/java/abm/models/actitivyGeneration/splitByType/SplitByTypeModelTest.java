package abm.models.actitivyGeneration.splitByType;

import abm.data.DataSet;
import abm.data.geo.Zone;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.data.pop.Relationship;
import abm.models.activityGeneration.splitByType.SplitByTypeModel;
import abm.properties.AbitResources;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;
import org.junit.Test;

public class SplitByTypeModelTest {

    final static Logger logger = Logger.getLogger(SplitByTypeModelTest.class);

    @Test
    public void test() {

        //set the working directory!
        AbitResources.initializeResources("abit.properties");

        DataSet dataSet = new DataSet();
        final Zone dummyZone = new Zone(1);
        dataSet.getZones().put(1, dummyZone);

        Household household = new Household(1, dummyZone, 1);
        Person person = new Person(1, household, 36, Gender.FEMALE,
                Relationship.married, Occupation.EMPLOYED, true, null, 10000,
                480, 480, 2000, null, Disability.WITHOUT);
        Plan.initializePlan(person);
        person.setHabitualMode( HabitualMode.CAR_DRIVER);
        Activity activity = new Activity(person, Purpose.ACCOMPANY);

        DiscretionaryActivityType discretionaryActivityType = new SplitByTypeModel(dataSet).assignActType(activity, person);

        logger.info(discretionaryActivityType);

    }

    @Test
    public void runSensitivityAnalysis(){

        //set the working directory!
        AbitResources.initializeResources("abit.properties");

        DataSet dataSet = new DataSet();
        final SplitByTypeModel splitByTypeModel = new SplitByTypeModel(dataSet);

        final Zone dummyZone = new Zone(1);
        dataSet.getZones().put(1, dummyZone);


        System.out.println("purpose,hh_size,probability");

        for (Purpose purpose : Purpose.getDiscretionaryPurposes()){
            for (int size = 1; size < 6; size ++){
                Household household = new Household(1, dummyZone, 1);
                Person person = null;
                for (int p = 1; p<= size; p++){
                    person = new Person(p, household, 36, Gender.FEMALE,
                            Relationship.married, Occupation.EMPLOYED, true, null, 10000,
                            480, 480, 2000, null, Disability.WITHOUT);
                    Plan.initializePlan(person);
                    Activity workActivity = new Activity(person, Purpose.WORK);
                    workActivity.setStartTime_min(9*60);
                    workActivity.setEndTime_min(18*60);
                    person.getPlan().getTours().put(8*60, new Tour(workActivity, person.getPlan().getTours().size() + 1));
                    person.setHabitualMode( HabitualMode.CAR_DRIVER);
                    household.getPersons().add(person);
                }

                Activity activity = new Activity(person, purpose);
                double utilityOfBeingOnMandatoryTour = splitByTypeModel.calculateUtilityOfBeingOnMandatoryTour(activity, person);
                double exp = Math.exp(utilityOfBeingOnMandatoryTour);
                double p = exp / (1 + exp);

                System.out.println(purpose + "," + size + "," + p);
            }

        }



    }


}
