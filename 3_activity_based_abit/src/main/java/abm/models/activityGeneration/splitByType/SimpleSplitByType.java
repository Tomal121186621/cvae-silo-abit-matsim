package abm.models.activityGeneration.splitByType;

import abm.utils.AbitUtils;
import abm.data.plans.*;
import abm.data.pop.Person;

import java.util.*;
import java.util.stream.Collectors;

public class SimpleSplitByType implements SplitByType {

    @Override
    public DiscretionaryActivityType assignActType(Activity activity, Person person) {

        List<DiscretionaryActivityType> discretionaryActivityTypeSet = new ArrayList<>();
        discretionaryActivityTypeSet.add(DiscretionaryActivityType.PRIMARY);

//        if (PlanTools.findMandatoryTour(person.getPlan()) != null ){
//            discretionaryActivityTypeSet.add(DiscretionaryActivityType.ON_MANDATORY_TOUR);
//        }

        final List<Tour> mandatoryTours = person.getPlan().getTours().values().stream().filter(tour -> Purpose.getMandatoryPurposes().contains(tour.getMainActivity().getPurpose())).collect(Collectors.toList());
        mandatoryTours.forEach(tour -> discretionaryActivityTypeSet.add(DiscretionaryActivityType.ON_MANDATORY_TOUR));


//        if (PlanTools.findDiscretionaryTour(person.getPlan()) != null ){
//            discretionaryActivityTypeSet.add(DiscretionaryActivityType.ON_DISCRETIONARY_TOUR);
//        }

        final List<Tour> discretionaryTours = person.getPlan().getTours().values().stream().filter(tour -> Purpose.getDiscretionaryPurposes().contains(tour.getMainActivity().getPurpose())).collect(Collectors.toList());
        discretionaryTours.forEach(tour -> discretionaryActivityTypeSet.add(DiscretionaryActivityType.ON_DISCRETIONARY_TOUR));


        Collections.shuffle(discretionaryActivityTypeSet, AbitUtils.getRandomObject());

        //first run split by type from MOP: mandatory tour or discretionary tour
        // if mandatory tour, return DiscretionaryActivityType.ON_MANDATORY_TOUR

        // if discretionary tour
        //need to figure out how to split between a primary and a stop on discretionary tour:
        // the first activity that is not in a discretionary tour has to be primary
        //the last one that is not in a discretionary tour may be more likely to be a stop instead of primary

        //check the final result in termns of #tours and #stops by tour


        return discretionaryActivityTypeSet.stream().findFirst().get();
    }

    @Override
    public DiscretionaryActivityType assignActTypeForDiscretionaryTourActs(Activity activity, Person person, int numActsNotOnMandatoryTours) {

        return null;
    }
}
