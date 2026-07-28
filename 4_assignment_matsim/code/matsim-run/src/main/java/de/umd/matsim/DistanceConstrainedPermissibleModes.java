package de.umd.matsim;

import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.population.Activity;
import org.matsim.api.core.v01.population.Plan;
import org.matsim.core.population.PersonUtils;
import org.matsim.core.population.algorithms.PermissibleModesCalculator;
import org.matsim.core.router.TripStructureUtils;
import org.matsim.core.utils.geometry.CoordUtils;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.List;

/**
 * PermissibleModesCalculator for SubtourModeChoice with a hard MAX-DISTANCE cutoff on walk and bike.
 *
 * The ASC penalty alone floors walk/bike well above the RTS targets (walk ~5.8% vs 2.8%, bike ~2.5% vs
 * 0.8%) because a constant can't fully suppress non-motorized on MEDIUM trips without absurd values.
 * A hard distance cutoff can: walk is removed from an agent's choice set when the agent's LONGEST trip
 * (crow-fly origin->destination) exceeds walkMaxDist, bike when it exceeds bikeMaxDist. Medium/long trips
 * are then only car/ride/pt and shift to car; walk/bike collapse to their genuine short-trip share.
 *
 * Car availability is still honoured (car removed when carAvail=never), matching the default calculator.
 * Distance is evaluated per plan via the longest trip (TripStructureUtils collapses stage activities).
 */
public class DistanceConstrainedPermissibleModes implements PermissibleModesCalculator {

    private final List<String> allModes;
    private final double walkMaxDist;
    private final double bikeMaxDist;

    public DistanceConstrainedPermissibleModes(String[] modes, double walkMaxDist, double bikeMaxDist) {
        this.allModes = Arrays.asList(modes);
        this.walkMaxDist = walkMaxDist;
        this.bikeMaxDist = bikeMaxDist;
    }

    @Override
    public Collection<String> getPermissibleModes(Plan plan) {
        List<String> modes = new ArrayList<>(allModes);

        // car availability (as the default PermissibleModesCalculatorImpl does)
        if ("never".equals(PersonUtils.getCarAvail(plan.getPerson()))) {
            modes.remove("car");
        }

        // longest crow-fly trip in the plan (stage activities collapsed by TripStructureUtils)
        double maxDist = 0.0;
        for (TripStructureUtils.Trip trip : TripStructureUtils.getTrips(plan)) {
            Coord o = trip.getOriginActivity().getCoord();
            Coord d = trip.getDestinationActivity().getCoord();
            if (o != null && d != null) {
                maxDist = Math.max(maxDist, CoordUtils.calcEuclideanDistance(o, d));
            }
        }
        if (maxDist > walkMaxDist) modes.remove("walk");
        if (maxDist > bikeMaxDist) modes.remove("bike");
        return modes;
    }
}
