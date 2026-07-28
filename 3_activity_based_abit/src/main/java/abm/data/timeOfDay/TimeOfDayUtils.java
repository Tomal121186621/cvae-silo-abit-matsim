package abm.data.timeOfDay;


import abm.properties.InternalProperties;

public class TimeOfDayUtils {


    private static final int MAX_VALUE = 7 * 24 * 60;


    /**
     * Converts the departure time distribution to a modified version of it where non-available time windows have a probability of zero
     *
     * @param originalTOD
     * @param availableTOD
     * @return
     */
    public static TimeOfWeekDistribution updateTODWithAvailability(TimeOfWeekDistribution originalTOD,
                                                                   AvailableTimeOfWeek availableTOD) {

        TimeOfWeekDistribution newTOD = new TimeOfWeekDistribution();
        for (int minute : originalTOD.getMinutes()) {
            newTOD.setProbability(minute, originalTOD.probability(minute) * (double) availableTOD.isAvailable(minute));
        }
        return newTOD;
    }

    public static TimeOfWeekDistribution updateTODWithAvailability(TimeOfWeekDistribution originalTOD,
                                                                   BlockedTimeOfWeekLinkedList blockedTOD) {

        TimeOfWeekDistribution newTOD = new TimeOfWeekDistribution();
        for (int minute : originalTOD.getMinutes()) {
            newTOD.setProbability(minute, originalTOD.probability(minute) * (double) blockedTOD.isAvailable(minute));
        }
        return newTOD;
    }

    public static TimeOfWeekDistribution updateTODWithAvailabilityAndDuration(TimeOfWeekDistribution originalTOD,
                                                                              BlockedTimeOfWeekLinkedList blockedTOD,
                                                                              int duration) {

        TimeOfWeekDistribution newTOD = new TimeOfWeekDistribution();
        for (int minute : originalTOD.getMinutes()) {
            boolean runThrough = true;
            for (int endMinute = minute; endMinute <= minute + duration; endMinute += InternalProperties.SEARCH_INTERVAL_MIN) {
                if (blockedTOD.isAvailable(endMinute) == 0) {
                    newTOD.setProbability(minute, 0);
                    runThrough = false;
                    break;
                }
            }
            if (runThrough) {
                newTOD.setProbability(minute, originalTOD.probability(minute));
            }
        }
        return newTOD;
    }


    /**
     * Converts the available time object to a new one that can accomodate a trip of certain duration. It avoids starting a trip that will overlap
     * with an already existing one
     *
     * @param baseAvailableTOD
     * @param tripDuration
     * @return
     */
    public static AvailableTimeOfWeek updateAvailableTimeForNextTrip(AvailableTimeOfWeek baseAvailableTOD,
                                                                     int tripDuration) {

        AvailableTimeOfWeek newAvailableTOD = new AvailableTimeOfWeek();

        for (int minute = InternalProperties.SEARCH_INTERVAL_MIN; minute < MAX_VALUE; minute = minute + InternalProperties.SEARCH_INTERVAL_MIN) {
            if (baseAvailableTOD.isAvailable(minute) == 0 && baseAvailableTOD.isAvailable(minute - InternalProperties.SEARCH_INTERVAL_MIN) == 1) {
                newAvailableTOD.blockTime(Math.max(0, minute - tripDuration), minute);
            } else if (baseAvailableTOD.isAvailable(minute) == 0) {
                newAvailableTOD.blockTime(minute - InternalProperties.SEARCH_INTERVAL_MIN, minute);
            }
        }
        return newAvailableTOD;
    }

    public static BlockedTimeOfWeekLinkedList updateAvailableTimeForNextTrip(BlockedTimeOfWeekLinkedList baseBlockedTOD,
                                                                             int tripDuration) {

        BlockedTimeOfWeekLinkedList newBlockedTOD = new BlockedTimeOfWeekLinkedList();

        for (int minute = InternalProperties.SEARCH_INTERVAL_MIN; minute < MAX_VALUE; minute = minute + InternalProperties.SEARCH_INTERVAL_MIN) {
            if (baseBlockedTOD.isAvailable(minute) == 0 && baseBlockedTOD.isAvailable(minute - InternalProperties.SEARCH_INTERVAL_MIN) == 1) {
                newBlockedTOD.blockTime(Math.max(0, minute - tripDuration), minute);
            } else if (baseBlockedTOD.isAvailable(minute) == 0) {
                newBlockedTOD.blockTime(minute - InternalProperties.SEARCH_INTERVAL_MIN, minute);
            }
        }
        return newBlockedTOD;
    }


}
