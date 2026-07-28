package abm.models.activityGeneration.frequency;

import abm.data.plans.Purpose;
import abm.data.pop.Person;

public class SimpleFrequencyGenerator implements FrequencyGenerator {
    @Override
    public int calculateNumberOfActivitiesPerWeek(Person person, Purpose purpose) {

        switch (purpose){
            case WORK:
                return 3;
            case EDUCATION:
                return 1;
            case RECREATION:
                return 3;
            case OTHER:
                return 3;
            case SHOPPING:
                return 2;
            case ACCOMPANY:
                return 8;
            default:
                throw new RuntimeException("Not possible");
        }
    }
}
