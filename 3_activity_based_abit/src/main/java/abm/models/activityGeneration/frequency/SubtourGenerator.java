package abm.models.activityGeneration.frequency;

import abm.data.plans.Activity;
import abm.data.plans.Tour;

public interface SubtourGenerator {

    boolean hasSubtourInMandatoryActivity(Tour mandatoryTour);

}
