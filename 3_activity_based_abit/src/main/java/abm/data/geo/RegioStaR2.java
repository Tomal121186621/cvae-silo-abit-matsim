package abm.data.geo;

//Todo: ask Joanna for double checking the regio type definition
public enum RegioStaR2 {

    URBAN(1),
    RURAL(2);

    private final int code;

    RegioStaR2(int code) {
        this.code = code;
    }

    public static RegioStaR2 valueOf(int code) {
        switch (code) {
            case 1:
                return URBAN;
            case 2:
                return RURAL;
            default:
                throw new RuntimeException("Area Type for code " + code + " not specified in SGtyp classification.");
        }
    }

    public int code() {
        return code;
    }

}
