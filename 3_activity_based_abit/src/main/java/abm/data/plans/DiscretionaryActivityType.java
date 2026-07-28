package abm.data.plans;

import java.util.HashSet;
import java.util.Set;

public enum DiscretionaryActivityType {

    //ON_MANDATORY_TOUR, PRIMARY, ON_DISCRETIONARY_TOUR;

    ON_MANDATORY_TOUR,
    PRIMARY,
    ON_DISCRETIONARY_TOUR,
    ACCOMPANY_PRIMARY,
    SHOP_PRIMARY,
    OTHER_PRIMARY,
    RECREATION_PRIMARY,
    ACCOMPANY_ON_ACCOMPANY,
    SHOP_ON_ACCOMPANY,
    SHOP_ON_SHOP,
    OTHER_ON_ACCOMPANY,
    OTHER_ON_SHOP,
    OTHER_ON_OTHER,
    RECREATION_ON_ACCOMPANY,
    RECREATION_ON_SHOP,
    RECREATION_ON_OTHER,
    RECREATION_ON_RECREATION;

    public static Set<DiscretionaryActivityType> getDiscretionaryOntoDiscretionaryTypes(){
        Set<DiscretionaryActivityType> activityTypes = new HashSet<>();
        activityTypes.add(ACCOMPANY_ON_ACCOMPANY);
        activityTypes.add(SHOP_ON_ACCOMPANY);
        activityTypes.add(SHOP_ON_SHOP);
        activityTypes.add(OTHER_ON_ACCOMPANY);
        activityTypes.add(OTHER_ON_SHOP);
        activityTypes.add(OTHER_ON_OTHER);
        activityTypes.add(RECREATION_ON_ACCOMPANY);
        activityTypes.add(RECREATION_ON_SHOP);
        activityTypes.add(RECREATION_ON_OTHER);
        activityTypes.add(RECREATION_ON_RECREATION);
        return activityTypes;
    }



}
