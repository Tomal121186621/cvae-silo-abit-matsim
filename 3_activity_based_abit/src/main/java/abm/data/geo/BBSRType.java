package abm.data.geo;

import de.tum.bgu.msm.data.AreaTypes;

public enum BBSRType {

    CORE_CITY(10),
    MEDIUM_SIZED_CITY(20),
    TOWN(30),
    RURAL(40);

    private final int code;

    BBSRType(int code) {
        this.code = code;
    }

    public static BBSRType valueOf(int code) {
        switch (code) {
            case 10:
                return CORE_CITY;
            case 20:
                return MEDIUM_SIZED_CITY;
            case 30:
                return TOWN;
            case 40:
                return RURAL;
            default:
                throw new RuntimeException("Area Type for code " + code + " not specified in SGtyp classification.");
        }
    }

    public int code() {
        return code;
    }

}
