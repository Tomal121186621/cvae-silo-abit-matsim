package abm.models.activityGeneration.time;

import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.pop.Person;

import java.time.DayOfWeek;

public interface DayOfWeekMandatoryAssignment {

    DayOfWeek[] assignDaysOfWeek(int numberOfActivities, Purpose purpose, Person person);

}
