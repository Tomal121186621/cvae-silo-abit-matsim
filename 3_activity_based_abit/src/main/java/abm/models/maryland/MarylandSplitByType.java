package abm.models.maryland;

import abm.data.plans.Activity;
import abm.data.plans.DiscretionaryActivityType;
import abm.data.pop.Person;
import abm.models.activityGeneration.splitByType.SplitByType;

/**
 * Every discretionary activity becomes its own home-based (PRIMARY) tour, matching the RTS structure
 * where SHOP/OTHER/RECREATION/ACCOMPANY are home-based tours. Intermediate stops are added separately
 * by the RTS ordered-logit {@link MarylandStopModel}, so no activities are turned into simple-split stops.
 */
public class MarylandSplitByType implements SplitByType {
    @Override
    public DiscretionaryActivityType assignActType(Activity activity, Person person) {
        return DiscretionaryActivityType.PRIMARY;
    }

    @Override
    public DiscretionaryActivityType assignActTypeForDiscretionaryTourActs(Activity activity, Person person, int n) {
        return DiscretionaryActivityType.PRIMARY;
    }
}
