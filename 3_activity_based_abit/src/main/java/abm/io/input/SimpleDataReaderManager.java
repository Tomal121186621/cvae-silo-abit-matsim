package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.MicroscopicLocation;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.data.pop.Relationship;
import abm.data.travelInformation.SimpleTravelDistances;
import abm.data.travelInformation.SimpleTravelTimes;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;

public class SimpleDataReaderManager implements DataReaderManager {


    private int numberOfHouseholds;

    public SimpleDataReaderManager(int numberOfHouseholds) {
        this.numberOfHouseholds = numberOfHouseholds;
    }

    @Override
    public DataSet readData() {
        DataSet dataSet = new DataSet();


        for (int i = 0; i < numberOfHouseholds; i++ ){
            MicroscopicLocation homeLocation = new MicroscopicLocation((AbitUtils.randomObject.nextDouble() - 0.5) * 3000,
                    (AbitUtils.randomObject.nextDouble() - 0.5)* 3000);
            Household household = new Household(i, homeLocation, 1);
            Person person = new Person(i, household, 25, Gender.FEMALE, Relationship.single, Occupation.EMPLOYED, true, null,
                    1000, 480, 480, 2000, null, Disability.WITHOUT);


            household.getPersons().add(person);
            dataSet.getHouseholds().put(household.getId(), household);
            dataSet.getPersons().put(person.getId(), person);
        }


        dataSet.setTravelTimes(new SimpleTravelTimes());
        dataSet.setTravelDistances(new SimpleTravelDistances());

        return dataSet;

    }

}
