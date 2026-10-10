package stats

import (
	"errors"
	"math"
	"testing"
)

func legacyFloatApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	if math.IsInf(a, 0) && math.IsInf(b, 0) && (math.Signbit(a) == math.Signbit(b)) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func legacyCoordsApproxEqual(a, b []Coordinate) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if !legacyFloatApproxEqual(a[i].X, b[i].X) || !legacyFloatApproxEqual(a[i].Y, b[i].Y) {
			return false
		}
	}
	return true
}

func TestExpReg(t *testing.T) {
	data := []Coordinate{{0, 1}, {1, 2}, {2, 4}}
	exp, errExp := ExponentialRegression(data)
	if errExp != nil {
		t.Fatalf("ExponentialRegression returned error: %v", errExp)
	}
	got, errGot := ExpReg(data)
	if errGot != nil {
		t.Fatalf("ExpReg returned error: %v", errGot)
	}
	if !legacyCoordsApproxEqual(exp, got) {
		t.Fatalf("ExpReg result mismatch. expected %v, got %v", exp, got)
	}
}

func TestLinReg(t *testing.T) {
	data := []Coordinate{{0, 0}, {1, 2}, {2, 4}}
	exp, errExp := LinearRegression(data)
	if errExp != nil {
		t.Fatalf("LinearRegression returned error: %v", errExp)
	}
	got, errGot := LinReg(data)
	if errGot != nil {
		t.Fatalf("LinReg returned error: %v", errGot)
	}
	if !legacyCoordsApproxEqual(exp, got) {
		t.Fatalf("LinReg result mismatch. expected %v, got %v", exp, got)
	}
}

func TestLogReg(t *testing.T) {
	data := []Coordinate{{1, 0}, {2, 0.6931471805599453}, {3, 1.0986122886681098}}
	exp, errExp := LogarithmicRegression(data)
	if errExp != nil {
		t.Fatalf("LogarithmicRegression returned error: %v", errExp)
	}
	got, errGot := LogReg(data)
	if errGot != nil {
		t.Fatalf("LogReg returned error: %v", errGot)
	}
	if !legacyCoordsApproxEqual(exp, got) {
		t.Fatalf("LogReg result mismatch. expected %v, got %v", exp, got)
	}
}

func TestStdDevP(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	exp, errExp := StandardDeviationPopulation(data)
	if errExp != nil {
		t.Fatalf("StandardDeviationPopulation returned error: %v", errExp)
	}
	got, errGot := StdDevP(data)
	if errGot != nil {
		t.Fatalf("StdDevP returned error: %v", errGot)
	}
	if !legacyFloatApproxEqual(exp, got) {
		t.Fatalf("StdDevP result mismatch. expected %v, got %v", exp, got)
	}
}

func TestStdDevS(t *testing.T) {
	data := Float64Data{2, 4, 4, 4, 5, 5, 7, 9}
	exp, errExp := StandardDeviationSample(data)
	if errExp != nil {
		t.Fatalf("StandardDeviationSample returned error: %v", errExp)
	}
	got, errGot := StdDevS(data)
	if errGot != nil {
		t.Fatalf("StdDevS returned error: %v", errGot)
	}
	if !legacyFloatApproxEqual(exp, got) {
		t.Fatalf("StdDevS result mismatch. expected %v, got %v", exp, got)
	}
}

func TestVarP(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
	}{
		{name: "empty", input: Float64Data{}},
		{name: "single", input: Float64Data{42.0}},
		{name: "multiple", input: Float64Data{1, 2, 3, 4, 5}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := VarP(tc.input)
			want, wantErr := PopulationVariance(tc.input)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error presence mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil {
				if !errors.Is(err, wantErr) {
					t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
				}
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("variance mismatch: got %v, want %v", got, want)
			}
		})
	}
}

func TestVarS(t *testing.T) {
	cases := []struct {
		name  string
		input Float64Data
	}{
		{name: "empty", input: Float64Data{}},
		{name: "single", input: Float64Data{42.0}},
		{name: "multiple", input: Float64Data{1, 2, 3, 4, 5}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := VarS(tc.input)
			want, wantErr := SampleVariance(tc.input)
			if (err != nil) != (wantErr != nil) {
				t.Fatalf("error presence mismatch: got %v, want %v", err, wantErr)
			}
			if err != nil {
				if !errors.Is(err, wantErr) {
					t.Fatalf("error mismatch: got %v, want %v", err, wantErr)
				}
				return
			}
			if math.Abs(got-want) > 1e-9 {
				t.Fatalf("variance mismatch: got %v, want %v", got, want)
			}
		})
	}
}
