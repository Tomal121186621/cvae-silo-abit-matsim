package abm.models.destinationChoice;

import abm.data.plans.Activity;

public class SimpleSubtourDestination implements SubtourDestinationChoice {
    @Override
    public void chooseSubtourDestination(Activity subtourActivity, Activity mainActivity) {
        subtourActivity.setLocation(mainActivity.getLocation());
    }
}
