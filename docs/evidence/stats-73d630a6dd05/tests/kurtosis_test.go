package stats

import (
	"errors"
	"math"
	"testing"
)

func kurtosisApproxEqual(a, b float64) bool {
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= 1e-9
}

func TestPopulationKurtosis_ErrorsAndValues(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		want    float64
		wantErr error
	}{
		{"empty", []float64{}, math.NaN(), ErrEmptyInput},
		{"single", []float64{1}, math.NaN(), ErrEmptyInput},
		{"all equal", []float64{5, 5, 5, 5}, math.NaN(), ErrZero},
		{"two‑point", []float64{1, -1, 1, -1}, -2.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationKurtosis(Float64Data(tc.input))
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil && !kurtosisApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestSampleKurtosis_ErrorsAndValues(t *testing.T) {
	cases := []struct {
		name    string
		input   []float64
		want    float64
		wantErr error
	}{
		{"too few", []float64{1, 2, 3}, math.NaN(), ErrEmptyInput},
		{"all equal", []float64{2, 2, 2, 2}, math.NaN(), ErrZero},
		{"two‑point", []float64{1, -1, 1, -1}, -6.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleKurtosis(Float64Data(tc.input))
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if tc.wantErr == nil && !kurtosisApproxEqual(got, tc.want) {
				t.Fatalf("unexpected result: got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestKurtosis_Forward(t *testing.T) {
	data := Float64Data{1, -1, 1, -1}
	want, _ := PopulationKurtosis(data)
	got, err := Kurtosis(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !kurtosisApproxEqual(got, want) {
		t.Fatalf("forwarding mismatch: got %v, want %v", got, want)
	}
}

func TestFloat64Data_Kurtosis(t *testing.T) {
	data := Float64Data{1, -1, 1, -1}
	want, _ := PopulationKurtosis(data)
	got, err := data.Kurtosis()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !kurtosisApproxEqual(got, want) {
		t.Fatalf("method mismatch: got %v, want %v", got, want)
	}
}

func TestFloat64Data_PopulationKurtosis(t *testing.T) {
	data := Float64Data{1, -1, 1, -1}
	want, _ := PopulationKurtosis(data)
	got, err := data.PopulationKurtosis()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !kurtosisApproxEqual(got, want) {
		t.Fatalf("method mismatch: got %v, want %v", got, want)
	}
}

func TestFloat64Data_SampleKurtosis(t *testing.T) {
	cases := []struct {
		name    string
		data    []float64
		wantErr bool
	}{
		{"normal", []float64{1, 2, 3, 4, 5}, false},
		{"empty", []float64{}, true},
		{"single", []float64{1}, true},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			f := Float64Data(tc.data)
			got, err := f.SampleKurtosis()
			if tc.wantErr {
				if err == nil {
					t.Fatalf("expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			// compare with the package-level function to ensure wrapper works
			exp, err2 := SampleKurtosis(tc.data)
			if err2 != nil {
				t.Fatalf("unexpected error from SampleKurtosis: %v", err2)
			}
			if !kurtosisApproxEqual(got, exp) {
				t.Fatalf("SampleKurtosis wrapper returned %v, expected %v", got, exp)
			}
		})
	}
}
