package abm.data.plans;

import abm.data.geo.Location;
import abm.data.geo.MicroscopicLocation;
import abm.utils.AbitUtils;

public class Leg {

    private Activity previousActivity;
    private Activity nextActivity;
    private Mode legMode;
    private int travelTime_min;


    private double distance;

    public Leg(Activity previousActivity, Activity nextActivity) {
        this.previousActivity = previousActivity;
        this.nextActivity = nextActivity;
        this.legMode = Mode.UNKNOWN;
    }

    public Activity getPreviousActivity() {
        return previousActivity;
    }

    public void setPreviousActivity(Activity previousActivity) {
        this.previousActivity = previousActivity;
    }

    public Activity getNextActivity() {
        return nextActivity;
    }

    public void setNextActivity(Activity nextActivity) {
        this.nextActivity = nextActivity;
    }

    public Mode getLegMode() {
        return legMode;
    }

    public void setLegMode(Mode legMode) {
        this.legMode = legMode;
    }

    public int getTravelTime_min() {
        return travelTime_min;
    }

    public void setTravelTime_min(int travelTime_min) {
        this.travelTime_min = travelTime_min;
    }

    public double getDistance() {
        return distance;
    }

    public void setDistance(double distance) {
        this.distance = distance;
    }

    public String toString() {
        StringBuilder builder = new StringBuilder();

        builder.append(previousActivity.getPerson().getId()).append(AbitUtils.SEPARATOR);
        builder.append(previousActivity.getPurpose()).append(AbitUtils.SEPARATOR);
        if (previousActivity.getPurpose() != Purpose.HOME) {
            builder.append(previousActivity.getEndTime_min()).append(AbitUtils.SEPARATOR);
        } else {
            builder.append(nextActivity.getStartTime_min() - travelTime_min).append(AbitUtils.SEPARATOR);
        }

        MicroscopicLocation microscopicPreviousLocation = null;
        Location previousLocation = previousActivity.getLocation();
        if (previousLocation instanceof MicroscopicLocation) {
            microscopicPreviousLocation = (MicroscopicLocation) previousLocation;
            builder.append(microscopicPreviousLocation.getX()).append(AbitUtils.SEPARATOR);
            builder.append(microscopicPreviousLocation.getY()).append(AbitUtils.SEPARATOR);
        } else {
            builder.append(-1).append(AbitUtils.SEPARATOR);
            builder.append(-1).append(AbitUtils.SEPARATOR);
        }

        builder.append(previousLocation.getZoneId()).append(AbitUtils.SEPARATOR);

        builder.append(nextActivity.getPurpose()).append(AbitUtils.SEPARATOR);

        if (nextActivity.getPurpose() != Purpose.HOME) {
            builder.append(nextActivity.getStartTime_min()).append(AbitUtils.SEPARATOR);
        } else {
            builder.append(previousActivity.getEndTime_min() + travelTime_min).append(AbitUtils.SEPARATOR);
        }

        MicroscopicLocation microscopicNextLocation = null;
        Location nextLocation = nextActivity.getLocation();
        if (previousLocation instanceof MicroscopicLocation) {
            microscopicNextLocation = (MicroscopicLocation) nextLocation;
            builder.append(microscopicNextLocation.getX()).append(AbitUtils.SEPARATOR);
            builder.append(microscopicNextLocation.getY()).append(AbitUtils.SEPARATOR);
        } else {
            builder.append(-1).append(AbitUtils.SEPARATOR);
            builder.append(-1).append(AbitUtils.SEPARATOR);
        }

        builder.append(nextLocation.getZoneId()).append(AbitUtils.SEPARATOR);

        builder.append(legMode).append(AbitUtils.SEPARATOR);
        builder.append(travelTime_min).append(AbitUtils.SEPARATOR);

        if (microscopicNextLocation != null && microscopicPreviousLocation != null) {
            double distance = Math.abs(microscopicNextLocation.getX() - microscopicPreviousLocation.getX()) +
                    Math.abs(microscopicNextLocation.getY() - microscopicPreviousLocation.getY());
            builder.append(distance);
        } else {
            builder.append(-1);
        }

        if (nextActivity.getSubtour() != null){
            builder.append("\n");
            builder.append(nextActivity.getSubtour().getOutboundLeg().toString());
            builder.append("\n");
            builder.append(nextActivity.getSubtour().getInboundLeg().toString());

        }

        return builder.toString();
    }


    public static String getHeader() {
        StringBuilder builder = new StringBuilder();
        builder.append("person_id").append(AbitUtils.SEPARATOR);
        builder.append("previous_purpose").append(AbitUtils.SEPARATOR);
        builder.append("start_time_min").append(AbitUtils.SEPARATOR);
        builder.append("start_x").append(AbitUtils.SEPARATOR);
        builder.append("start_y").append(AbitUtils.SEPARATOR);
        builder.append("start_zone").append(AbitUtils.SEPARATOR);
        builder.append("next_purpose").append(AbitUtils.SEPARATOR);
        builder.append("end_time").append(AbitUtils.SEPARATOR);
        builder.append("end_x").append(AbitUtils.SEPARATOR);
        builder.append("end_y").append(AbitUtils.SEPARATOR);
        builder.append("end_zone").append(AbitUtils.SEPARATOR);
        builder.append("mode").append(AbitUtils.SEPARATOR);
        builder.append("time_min").append(AbitUtils.SEPARATOR);
        builder.append("distance_m");
        return builder.toString();
    }


}
