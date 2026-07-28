package abm.data.plans;

import java.util.SortedSet;
import java.util.TreeSet;

public enum HabitualMode {


    CAR_DRIVER,
    CAR_PASSENGER,
    PT,
    BIKE,
    WALK,
    UNKNOWN;


    //if someone needs to keep the mode UNKNOWN (but also allow for more mode set implementations,
    // e.g. with new modes such as ride hailing) it would be nice to extract an interface Mode and keep the enum
    // behind it, so the interface cannot access to Mode.values() (that someone could call by mistake now) for looping
    // across all modes, which would end up, e.g. looking for coefficients for Mode.UNKNOWN or final choices of it.
    // However, this may not be obvious because getModes() is here a static method but with the interface it
    // would be non-static, so an instance of the used Mode (here Mode as interface) shoudl exist e.g. in the dataset.

    public static SortedSet<HabitualMode> getHabitualModes() {
        SortedSet<HabitualMode> modes = new TreeSet<>();
        modes.add(CAR_DRIVER);
        modes.add(CAR_PASSENGER);
        modes.add(PT);
        modes.add(BIKE);
        modes.add(WALK);
        modes.add(UNKNOWN);
        return modes;
    }

    public static SortedSet<HabitualMode> getHabitualModesWithoutUnknown() {
        SortedSet<HabitualMode> modes = new TreeSet<>();
        modes.add(CAR_DRIVER);
        modes.add(CAR_PASSENGER);
        modes.add(PT);
        modes.add(BIKE);
        modes.add(WALK);
        return modes;
    }

}
