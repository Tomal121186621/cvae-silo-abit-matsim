package abm.models;

import abm.data.plans.Purpose;
import abm.io.input.BikeOwnershipReader;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.models.activityGeneration.frequency.SubtourGenerator;
import abm.models.activityGeneration.splitByType.SplitByType;
import abm.models.activityGeneration.splitByType.SplitStopType;
import abm.models.activityGeneration.time.DayOfWeekDiscretionaryAssignment;
import abm.models.activityGeneration.time.DayOfWeekMandatoryAssignment;
import abm.models.activityGeneration.time.SubtourTimeAssignment;
import abm.models.activityGeneration.time.TimeAssignment;
import abm.models.destinationChoice.DestinationChoice;
import abm.models.destinationChoice.SubtourDestinationChoice;
import abm.models.modeChoice.HabitualModeChoice;
import abm.models.modeChoice.SubtourModeChoice;
import abm.models.modeChoice.TourModeChoice;

import java.util.Map;

public interface ModelSetup {


    HabitualModeChoice getHabitualModeChoice();

    Map<Purpose, FrequencyGenerator> getFrequencyGenerator();

    DestinationChoice getDestinationChoice();

    TourModeChoice getTourModeChoice();

    DayOfWeekMandatoryAssignment getDayOfWeekMandatoryAssignment();

    DayOfWeekDiscretionaryAssignment getDayOfWeekDiscretionaryAssignment();

    TimeAssignment getTimeAssignment();

    SplitByType getSplitByType();

    SplitStopType getStopSplitType();

    SubtourGenerator getSubtourGenerator();

    SubtourTimeAssignment getSubtourTimeAssignment();

    SubtourDestinationChoice getSubtourDestinationChoice();

    SubtourModeChoice getSubtourModeChoice();

    // Default so Simple/Default setups (which have no bike-ownership model) still compile;
    // ModelSetupMuc overrides this.
    default BikeOwnershipReader getBikeOwnershipReader() {
        return null;
    }
}
