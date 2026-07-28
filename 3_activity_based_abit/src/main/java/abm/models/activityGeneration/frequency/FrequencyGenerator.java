package abm.models.activityGeneration.frequency;

import abm.data.plans.Purpose;
import abm.data.pop.Person;

public interface FrequencyGenerator {

    int calculateNumberOfActivitiesPerWeek(Person person, Purpose purpose);

}
