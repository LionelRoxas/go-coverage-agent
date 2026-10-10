package stats

import (
	"errors"
	"math"
	"testing"
)

func varianceApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestCovariance_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
	}{
		{"EmptyBoth", Float64Data{}, Float64Data{}, EmptyInputErr},
		{"EmptyFirst", Float64Data{}, Float64Data{1}, EmptyInputErr},
		{"SizeMismatch", Float64Data{1, 2}, Float64Data{1}, SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Covariance(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !math.IsNaN(got) {
				t.Fatalf("expected NaN result, got %v", got)
			}
		})
	}
}

func TestCovariance_Normal(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{4, 5, 6}
	got, err := Covariance(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := 1.0 // sample covariance
	if !varianceApproxEqual(got, want) {
		t.Fatalf("expected %v, got %v", want, got)
	}
}

func TestCovariancePopulation_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
	}{
		{"EmptyBoth", Float64Data{}, Float64Data{}, EmptyInputErr},
		{"SizeMismatch", Float64Data{1, 2}, Float64Data{1}, SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := CovariancePopulation(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !math.IsNaN(got) {
				t.Fatalf("expected NaN result, got %v", got)
			}
		})
	}
}

func TestCovariancePopulation_Normal(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{4, 5, 6}
	got, err := CovariancePopulation(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := 2.0 / 3.0 // population covariance
	if !varianceApproxEqual(got, want) {
		t.Fatalf("expected %v, got %v", want, got)
	}
}

func TestPopulationVariance_ErrorsAndNormal(t *testing.T) {
	// Error case
	if got, err := PopulationVariance(Float64Data{}); !errors.Is(err, EmptyInputErr) || !math.IsNaN(got) {
		t.Fatalf("expected EmptyInputErr and NaN, got %v, %v", got, err)
	}
	// Normal case
	data := Float64Data{1, 2, 3}
	got, err := PopulationVariance(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := 2.0 / 3.0 // population variance
	if !varianceApproxEqual(got, want) {
		t.Fatalf("expected %v, got %v", want, got)
	}
}

func TestSampleVariance_ErrorsAndNormal(t *testing.T) {
	// Error case
	if got, err := SampleVariance(Float64Data{}); !errors.Is(err, EmptyInputErr) || !math.IsNaN(got) {
		t.Fatalf("expected EmptyInputErr and NaN, got %v, %v", got, err)
	}
	// Normal case
	data := Float64Data{1, 2, 3}
	got, err := SampleVariance(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := 1.0 // sample variance (unbiased)
	if !varianceApproxEqual(got, want) {
		t.Fatalf("expected %v, got %v", want, got)
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
	if !varianceApproxEqual(got, want) {
		t.Fatalf("Variance should delegate to PopulationVariance; got %v, want %v", got, want)
	}
}
