package stats

import (
	"errors"
	"math"
	"testing"
)

func varianceApproxEqual(t *testing.T, got, want float64) {
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("got %v want %v", got, want)
	}
}

func TestCovariance(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, Float64Data{}, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, math.NaN(), SizeErr},
		{"simple", Float64Data{1, 2, 3}, Float64Data{4, 5, 6}, 1.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Covariance(tc.d1, tc.d2)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			varianceApproxEqual(t, got, tc.want)
		})
	}
}

func TestCovariancePopulation(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, Float64Data{}, math.NaN(), EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, math.NaN(), SizeErr},
		{"simple", Float64Data{1, 2, 3}, Float64Data{4, 5, 6}, 2.0 / 3.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CovariancePopulation(tc.d1, tc.d2)
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			varianceApproxEqual(t, got, tc.want)
		})
	}
}

func TestPopulationVariance_EmptyInput(t *testing.T) {
	_, err := PopulationVariance(Float64Data{})
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestSampleVariance_EmptyInput(t *testing.T) {
	_, err := SampleVariance(Float64Data{})
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
}

func TestVariance_Delegates(t *testing.T) {
	data := Float64Data{1, 2, 3, 4}
	got, err := Variance(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want, err2 := PopulationVariance(data)
	if err2 != nil {
		t.Fatalf("unexpected error from PopulationVariance: %v", err2)
	}
	varianceApproxEqual(t, got, want)
}
