package abm.models.modeChoice;

import abm.data.plans.Activity;
import abm.data.plans.Mode;
import abm.data.plans.Tour;

public class SimpleSubtourModeChoice implements SubtourModeChoice{
    @Override
    public void chooseSubtourMode(Tour tour) {
        tour.getMainActivity().getSubtour().getInboundLeg().setLegMode(Mode.WALK);
        tour.getMainActivity().getSubtour().getOutboundLeg().setLegMode(Mode.WALK);
    }
}
