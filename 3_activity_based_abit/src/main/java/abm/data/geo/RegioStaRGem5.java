package abm.data.geo;

//Todo: ask Joanna for double checking the regio type definition
public enum RegioStaRGem5 {

    METROPOLIS(51),
    REGIOPOLIS_LARGE_CITY(52),
    CENTRAL_CITY(53),
    URBAN_AREA(54),
    PROVINCIAL_RURAL(55);


    private final int code;

    RegioStaRGem5(int code) {
        this.code = code;
    }

    public static RegioStaRGem5 valueOf(int code) {
        switch (code) {
            case 51:
                return METROPOLIS;
            case 52:
                return REGIOPOLIS_LARGE_CITY;
            case 53:
                return CENTRAL_CITY;
            case 54:
                return URBAN_AREA;
            case 55:
                return PROVINCIAL_RURAL;
            default:
                throw new RuntimeException("Area Type for code " + code + " not specified in SGtyp classification.");
        }
    }

    public int code() {
        return code;
    }

}
