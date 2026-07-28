package abm.data.plans;

import abm.data.pop.Person;
import org.checkerframework.checker.units.qual.A;

public class Subtour {

    private Activity mainActivity;
    private Activity mainActivityPart1;
    private Activity mainActivityPart2;
    private Activity subtourActivity;

    private Leg outboundLeg;

    private Leg inboundLeg;
    public Subtour(Activity mainActivity, Activity subtourActivity, int travelTime_min) {
        this.mainActivity = mainActivity;
        this.mainActivityPart1 = new Activity(mainActivity.getPerson(), mainActivity.getPurpose());
        mainActivityPart1.setStartTime_min(mainActivity.getStartTime_min());
        mainActivityPart1.setLocation(mainActivity.getLocation());
        mainActivityPart1.setEndTime_min(subtourActivity.getStartTime_min() - travelTime_min);

        this.mainActivityPart2 = new Activity(mainActivity.getPerson(), mainActivity.getPurpose());
        mainActivityPart2.setEndTime_min(mainActivity.getEndTime_min());
        mainActivityPart2.setLocation(mainActivity.getLocation());
        mainActivityPart2.setStartTime_min(subtourActivity.getEndTime_min() + travelTime_min);

        this.subtourActivity = subtourActivity;
        this.outboundLeg = new Leg(mainActivityPart1, subtourActivity);
        this.inboundLeg = new Leg(subtourActivity, mainActivityPart2);
    }


    public Activity getMainActivity() {
        return mainActivity;
    }

    public Activity getSubtourActivity() {
        return subtourActivity;
    }

    public Leg getOutboundLeg() {
        return outboundLeg;
    }

    public Leg getInboundLeg() {
        return inboundLeg;
    }
}
