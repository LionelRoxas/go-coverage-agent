package stats

import (
	"errors"
	"math"
	"testing"
)

func kurtosisApproxEqual(got, want float64) bool {
	const eps = 1e-9
	return math.Abs(got-want) <= eps
}

func TestPopulationKurtosis(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"single", Float64Data{1.0}, math.NaN(), ErrEmptyInput},
		{"zero variance", Float64Data{2.0, 2.0, 2.0, 2.0}, math.NaN(), ErrZero},
		{"normal", Float64Data{1.0, 2.0, 3.0, 4.0, 5.0}, -1.3, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationKurtosis(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				if !kurtosisApproxEqual(got, tc.want) {
					t.Errorf("unexpected result: got %v, want %v", got, tc.want)
				}
			}
		})
	}
}

func TestSampleKurtosis(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"len<4", Float64Data{1.0, 2.0, 3.0}, math.NaN(), ErrEmptyInput},
		{"zero variance", Float64Data{2.0, 2.0, 2.0, 2.0}, math.NaN(), ErrZero},
		{"normal", Float64Data{1.0, 2.0, 3.0, 4.0, 5.0}, -1.2, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleKurtosis(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				if !kurtosisApproxEqual(got, tc.want) {
					t.Errorf("unexpected result: got %v, want %v", got, tc.want)
				}
			}
		})
	}
}

func TestKurtosis(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{"normal", Float64Data{1.0, 2.0, 3.0, 4.0, 5.0}, -1.3, nil},
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Kurtosis(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("unexpected error: got %v, want %v", err, tc.wantErr)
			}
			if err == nil {
				if !kurtosisApproxEqual(got, tc.want) {
					t.Errorf("unexpected result: got %v, want %v", got, tc.want)
				}
			}
		})
	}
}

func TestFloat64Data_Kurtosis(t *testing.T) {
	data := Float64Data{1.0, 2.0, 3.0, 4.0, 5.0}
	got, err := data.Kurtosis()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !kurtosisApproxEqual(got, -1.3) {
		t.Errorf("unexpected result: got %v, want %v", got, -1.3)
	}
}

func TestFloat64Data_PopulationKurtosis(t *testing.T) {
	data := Float64Data{1.0, 2.0, 3.0, 4.0, 5.0}
	got, err := data.PopulationKurtosis()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !kurtosisApproxEqual(got, -1.3) {
		t.Errorf("unexpected result: got %v, want %v", got, -1.3)
	}
}

func TestFloat64Data_SampleKurtosis(t *testing.T) {
	cases := []struct {
		name string
		data []float64
	}{
		{"Empty", []float64{}},
		{"Single", []float64{1.0}},
		{"Two", []float64{1.0, 2.0}},
		{"Four", []float64{1.0, 2.0, 3.0, 4.0}},
		{"Normal", []float64{2.0, 4.0, 6.0, 8.0, 10.0}},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			gotMethod, errMethod := Float64Data(tc.data).SampleKurtosis()
			gotFunc, errFunc := SampleKurtosis(tc.data)
			if errMethod != nil || errFunc != nil {
				if !errors.Is(errMethod, errFunc) {
					t.Errorf("different errors: method %v, func %v", errMethod, errFunc)
				}
				return
			}
			if !kurtosisApproxEqual(gotMethod, gotFunc) {
				t.Errorf("result mismatch: method %v, func %v", gotMethod, gotFunc)
			}
		})
	}
}
