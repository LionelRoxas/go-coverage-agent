package stats

import (
	"errors"
	"math"
	"testing"
)

func TestPopulationKurtosis_Errors(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr error
	}{
		{"empty input", Float64Data{}, ErrEmptyInput},
		{"zero variance", Float64Data{2, 2, 2, 2}, ErrZero},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationKurtosis(tc.data)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !math.IsNaN(got) {
				t.Fatalf("expected result NaN, got %v", got)
			}
		})
	}
}

func TestPopulationKurtosis_Normal(t *testing.T) {
	data := Float64Data{0, 1, 2, 3}
	got, err := PopulationKurtosis(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Expected value computed manually: -1.36 (within tolerance)
	want := -1.36
	if math.Abs(got-want) > 1e-2 {
		t.Fatalf("PopulationKurtosis = %v, want approx %v", got, want)
	}
}

func TestSampleKurtosis_Errors(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		wantErr error
	}{
		{"too few elements", Float64Data{1, 2, 3}, ErrEmptyInput},
		{"zero variance propagates", Float64Data{5, 5, 5, 5}, ErrZero},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleKurtosis(tc.data)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !math.IsNaN(got) {
				t.Fatalf("expected NaN result, got %v", got)
			}
		})
	}
}

func TestSampleKurtosis_Normal(t *testing.T) {
	data := Float64Data{0, 1, 2, 3}
	got, err := SampleKurtosis(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Population kurtosis for this data is approx -1.36, sample corrected should be approx -1.2
	want := -1.2
	if math.Abs(got-want) > 1e-2 {
		t.Fatalf("SampleKurtosis = %v, want approx %v", got, want)
	}
}

func TestKurtosis_Wrapper(t *testing.T) {
	// Wrapper should behave like PopulationKurtosis
	data := Float64Data{0, 1, 2, 3}
	want, err1 := PopulationKurtosis(data)
	if err1 != nil {
		t.Fatalf("PopulationKurtosis unexpected error: %v", err1)
	}
	got, err2 := Kurtosis(data)
	if err2 != nil {
		t.Fatalf("Kurtosis unexpected error: %v", err2)
	}
	if math.Abs(got-want) > 1e-12 {
		t.Fatalf("Kurtosis = %v, want %v", got, want)
	}
}

func TestFloat64Data_Kurtosis_Wrappers(t *testing.T) {
	data := Float64Data{0, 1, 2, 3}
	// Test method Kurtosis (population)
	wantPop, err1 := PopulationKurtosis(data)
	if err1 != nil {
		t.Fatalf("PopulationKurtosis error: %v", err1)
	}
	gotPop, err2 := data.Kurtosis()
	if err2 != nil {
		t.Fatalf("Float64Data.Kurtosis error: %v", err2)
	}
	if math.Abs(gotPop-wantPop) > 1e-12 {
		t.Fatalf("Float64Data.Kurtosis = %v, want %v", gotPop, wantPop)
	}
	// Test method PopulationKurtosis (same as above)
	gotPop2, err3 := data.PopulationKurtosis()
	if err3 != nil {
		t.Fatalf("Float64Data.PopulationKurtosis error: %v", err3)
	}
	if math.Abs(gotPop2-wantPop) > 1e-12 {
		t.Fatalf("Float64Data.PopulationKurtosis = %v, want %v", gotPop2, wantPop)
	}
}
