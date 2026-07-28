package abm.data.pop;

//Todo: Joanna, add the definitions from MOP
public enum AgeGroupFine {

    from0to18, from19to24, from25to29, from30to49, from50to59, from60to69, from70;

    public static AgeGroupFine assignAgeGroupFine(int age) {
        if (age <= 18) {
            return from0to18;
        } else if (age <= 24) {
            return from19to24;
        } else if (age <= 29) {
            return from25to29;
        } else if (age <= 49) {
            return from30to49;
        } else if (age <= 59) {
            return from50to59;
        } else if (age <= 69) {
            return from60to69;
        }else {
            return from70;
        }
    }


}
