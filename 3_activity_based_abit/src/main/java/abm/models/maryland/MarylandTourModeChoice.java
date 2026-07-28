package abm.models.maryland;

import abm.data.DataSet;
import abm.data.plans.Leg;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.modeChoice.TourModeChoice;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

/**
 * RTS-empirical tour mode choice. Samples the tour mode from the RTS mode-share observed for the
 * tour's PURPOSE (purpose-specific: e.g. EDUCATION is bus / car-passenger dominated). All legs of the
 * tour receive the chosen mode. Purpose-specific shares are read from the generated
 * rt_mode_by_purpose.csv (RTS-estimated).
 */
public class MarylandTourModeChoice implements TourModeChoice {

    private static final Map<Purpose, Map<Mode, Double>> shareByPurpose = new HashMap<>();
    private static boolean loaded = false;
    private final DataSet dataSet;
    private final Random rnd = AbitUtils.getRandomObject();

    public MarylandTourModeChoice(DataSet dataSet) {
        this.dataSet = dataSet;
        if (!loaded) load();
    }

    private static synchronized void load() {
        if (loaded) return;
        String f = AbitResources.instance.getString("rt.mode.by.purpose");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                Purpose p = Purpose.valueOf(r[0].trim().toUpperCase());
                Mode m = Mode.valueOf(r[1].trim());
                double s = Double.parseDouble(r[2].trim());
                shareByPurpose.computeIfAbsent(p, k -> new EnumMap<>(Mode.class)).put(m, s);
            }
        } catch (Exception e) {
            throw new RuntimeException("MarylandTourModeChoice load failed", e);
        }
        loaded = true;
    }

    @Override
    public void chooseMode(Person person, Tour tour) {
        Purpose purpose = tour.getMainActivity().getPurpose();
        Map<Mode, Double> shares = shareByPurpose.getOrDefault(purpose, shareByPurpose.get(Purpose.OTHER));
        Mode chosen = sample(shares);
        for (Leg leg : tour.getLegs().values()) leg.setLegMode(chosen);
        tour.setTourMode(chosen);
    }

    private Mode sample(Map<Mode, Double> shares) {
        double u = rnd.nextDouble(), cum = 0;
        Mode last = Mode.CAR_DRIVER;
        for (Map.Entry<Mode, Double> e : shares.entrySet()) {
            cum += e.getValue();
            last = e.getKey();
            if (u <= cum) return e.getKey();
        }
        return last;
    }

    @Override public void chooseMode(Person person, Tour tour, Purpose purpose) { chooseMode(person, tour); }
    @Override public Mode chooseMode(Person person, Tour tour, Purpose purpose, Boolean carAvailable) {
        chooseMode(person, tour); return tour.getTourMode();
    }
    @Override public void checkCarAvailabilityAndChooseMode(Household h, Person p, Tour t, Purpose pu) { chooseMode(p, t); }
}
