package abm.models.activityGeneration.splitByType;

import abm.utils.AbitUtils;
import abm.data.plans.Activity;
import abm.data.plans.StopType;
import abm.data.plans.Tour;
import abm.data.pop.Person;

public class SimpleSplitStopType implements SplitStopType {

    @Override
    public StopType getStopType(Person person, Activity activity, Tour tour){
        boolean isBefore = AbitUtils.getRandomObject().nextBoolean();
        if (isBefore){
          return StopType.BEFORE;
        } else {
            return StopType.AFTER;
        }
    }

}
