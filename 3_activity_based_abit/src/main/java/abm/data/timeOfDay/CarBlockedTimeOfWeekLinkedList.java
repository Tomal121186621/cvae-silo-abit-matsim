package abm.data.timeOfDay;

import abm.properties.InternalProperties;

import java.time.DayOfWeek;
import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;


/**
 * This class defines a map of availability, with a key start time in minutes of the time window and a value boolean that defines
 * if the window is available (true) or not (false)
 **/

public class CarBlockedTimeOfWeekLinkedList {


    private LinkedList<Integer> internalList;
    private static final int MAX_VALUE = (int) (7 * 24 * 60);


    public CarBlockedTimeOfWeekLinkedList() {
        internalList = new LinkedList<Integer>();
    }

    public void blockTime(int from, int until) {

        int startIndex = (int) (Math.floor((double) from / InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN);
        int toIndex = (int) (Math.ceil((double) until / InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN);
        for (int i = startIndex; i <= toIndex; i = i + InternalProperties.SEARCH_INTERVAL_MIN) {
            if (!internalList.contains(i)) {
                internalList.add(i);
            }
        }

    }

    public void setAvailable(int from, int to) {

        for (int minute = from; minute <= to; minute++) {
            if (internalList.contains(minute)) {
                internalList.remove(minute);
            }
        }

    }

    public int isAvailable(int minute) {
        if (internalList.contains(minute)) {
            return 0;
        } else {
            int newIndex = Math.round(minute / InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN;
            if (internalList.contains(newIndex)) {
                return 0;
            }
        }
        return 1;
    }

    public boolean isAvailable(int startMinute, int endMinute) {

        int startIndex = (int) (Math.floor((double) startMinute / InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN);
        int toIndex = (int) (Math.ceil((double) endMinute / InternalProperties.SEARCH_INTERVAL_MIN) * InternalProperties.SEARCH_INTERVAL_MIN);

        for (int minute = startIndex; minute <= toIndex; minute++) {
            if (internalList.contains(minute)) {
                return Boolean.FALSE;
            }
        }
        return Boolean.TRUE;
    }

    public List<Integer> getMinutes() {
        return new ArrayList<>(internalList);
    }


    public CarBlockedTimeOfWeekLinkedList getForThisDayOfWeek(DayOfWeek dayOfWeek) {
        int midnightBefore = (dayOfWeek.ordinal()) * 24 * 60;
        CarBlockedTimeOfWeekLinkedList availableTimeOfDay = new CarBlockedTimeOfWeekLinkedList();

        this.internalList.forEach(m -> {
            if (m > midnightBefore && m < midnightBefore + 60 * 24) {
                if (this.internalList.contains(m)) {
                    availableTimeOfDay.internalList.add(m);
                }
            }
        });

        return availableTimeOfDay;
    }


    /*@Override
    public String toString() {
        StringBuilder value =  new StringBuilder();
        internalMap.values().forEach(v-> value.append(v?1:0));
        return value.toString();
    }*/

    public LinkedList<Integer> getInternalList() {
        return internalList;
    }

    public void resetCarBlockedTimeOfWeekLinkedList() {
    	internalList.clear();
    }
}
