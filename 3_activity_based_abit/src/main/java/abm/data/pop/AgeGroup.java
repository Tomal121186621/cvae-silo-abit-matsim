package abm.data.pop;

public enum AgeGroup {

    from0to18, from19to29, from30to49, from50to59, from60to69, from70;

    public static AgeGroup assignAgeGroup(int age) {
        if (age <= 18) {
            return from0to18;
        } else if (age <= 29) {
            return from19to29;
        } else if (age <= 49) {
            return from30to49;
        } else if (age <= 59) {
            return from50to59;
        } else if (age <= 69) {
            return from60to69;
        } else {
            return from70;
        }
    }
}
