package abm.models;

import abm.data.DataSet;
import abm.data.plans.Purpose;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.models.activityGeneration.frequency.SimpleSubtourGenerator;
import abm.models.activityGeneration.frequency.SubtourGenerator;
import abm.models.maryland.MarylandSplitByType;
import abm.models.activityGeneration.splitByType.SimpleSplitStopTypeModelWithAvailability;
import abm.models.activityGeneration.splitByType.SplitByType;
import abm.models.activityGeneration.splitByType.SplitStopType;
import abm.models.activityGeneration.time.*;
import abm.models.destinationChoice.DestinationChoice;
import abm.models.destinationChoice.SimpleSubtourDestination;
import abm.models.destinationChoice.SubtourDestinationChoice;
import abm.models.maryland.MarylandDestinationChoice;
import abm.models.maryland.MarylandFrequencyGenerator;
import abm.models.maryland.MarylandFullModeChoice;
import abm.models.modeChoice.*;
import org.apache.commons.collections.map.HashedMap;

import java.util.Map;

/**
 * Maryland single-day model setup: RTS-empirical daily models (frequency, tour mode, destination)
 * fed by generated RTS parameter files + real OMX LOS, with Simple weekly/stop/subtour components
 * (single representative weekday, per the MATSim 24h requirement).
 */
public class ModelSetupMaryland implements ModelSetup {

    private final Map<Purpose, FrequencyGenerator> frequencyGenerators;
    private final HabitualModeChoice habitualModeChoice;
    private final DestinationChoice destinationChoice;
    private final TourModeChoice tourModeChoice;
    private final DayOfWeekMandatoryAssignment dayOfWeekMandatoryAssignment;
    private final DayOfWeekDiscretionaryAssignment dayOfWeekDiscretionaryAssignment;
    private final TimeAssignment timeAssignment;
    private final SplitByType splitByType;
    private final SplitStopType stopSplitType;
    private final SubtourGenerator subtourGenerator;
    private final SubtourTimeAssignment subtourTimeAssignment;
    private final SubtourDestinationChoice subtourDestinationChoice;
    private final SubtourModeChoice subtourModeChoice;

    public ModelSetupMaryland(DataSet dataSet) {
        stopSplitType = new SimpleSplitStopTypeModelWithAvailability();
        splitByType = new MarylandSplitByType();
        timeAssignment = new abm.models.maryland.MarylandTimeAssignment(); // RTS purpose-specific start + duration
        // weekday-concentrated work (a work tour on every weekday) + weekday-scattered discretionary,
        // so the extracted representative weekday reproduces the RTS daily by-purpose tour mix.
        dayOfWeekMandatoryAssignment = new abm.models.maryland.MarylandDayOfWeekMandatoryAssignment();
        dayOfWeekDiscretionaryAssignment = new abm.models.maryland.MarylandDayOfWeekDiscretionaryAssignment();
        habitualModeChoice = new SimpleHabitualModeChoice();

        destinationChoice = new MarylandDestinationChoice(dataSet);
        tourModeChoice = new MarylandFullModeChoice(dataSet);   // full Chayan & Cirillo 2024 MNL (price-elastic)
        frequencyGenerators = new HashedMap();
        for (Purpose purpose : Purpose.getAllPurposes()) {
            frequencyGenerators.put(purpose, new MarylandFrequencyGenerator());
        }

        subtourGenerator = new SimpleSubtourGenerator();
        subtourTimeAssignment = new SimpleSubtourTimeAssignment();
        subtourDestinationChoice = new SimpleSubtourDestination();
        subtourModeChoice = new SimpleSubtourModeChoice();
    }

    public HabitualModeChoice getHabitualModeChoice() { return habitualModeChoice; }
    public Map<Purpose, FrequencyGenerator> getFrequencyGenerator() { return frequencyGenerators; }
    public DestinationChoice getDestinationChoice() { return destinationChoice; }
    public TourModeChoice getTourModeChoice() { return tourModeChoice; }
    public DayOfWeekMandatoryAssignment getDayOfWeekMandatoryAssignment() { return dayOfWeekMandatoryAssignment; }
    public DayOfWeekDiscretionaryAssignment getDayOfWeekDiscretionaryAssignment() { return dayOfWeekDiscretionaryAssignment; }
    public TimeAssignment getTimeAssignment() { return timeAssignment; }
    public SplitByType getSplitByType() { return splitByType; }
    public SplitStopType getStopSplitType() { return stopSplitType; }
    public SubtourGenerator getSubtourGenerator() { return subtourGenerator; }
    public SubtourTimeAssignment getSubtourTimeAssignment() { return subtourTimeAssignment; }
    public SubtourDestinationChoice getSubtourDestinationChoice() { return subtourDestinationChoice; }
    public SubtourModeChoice getSubtourModeChoice() { return subtourModeChoice; }
}
