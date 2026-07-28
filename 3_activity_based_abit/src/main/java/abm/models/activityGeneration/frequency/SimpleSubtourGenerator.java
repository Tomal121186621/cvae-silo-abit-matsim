package abm.models.activityGeneration.frequency;

import abm.data.plans.Activity;
import abm.data.plans.Tour;
import abm.utils.AbitUtils;

public class SimpleSubtourGenerator implements SubtourGenerator {
    @Override
    public boolean hasSubtourInMandatoryActivity(Tour mandatoryTour) {
        if ( AbitUtils.getRandomObject().nextDouble() < 0.05){
            return true;
        } else {
            return false;
        }
    }
}
