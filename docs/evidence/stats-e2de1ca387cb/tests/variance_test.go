package stats

import (
	"errors"
	"math"
	"testing"
)

func TestCovariance_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
	}{
		{"empty first", Float64Data{}, Float64Data{1, 2}, EmptyInputErr},
		{"empty second", Float64Data{1, 2}, Float64Data{}, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := Covariance(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestCovariance_Normal(t *testing.T) {
	d1 := Float64Data{2, 4, 6, 8}
	d2 := Float64Data{1, 3, 5, 7}
	got, err := Covariance(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	mean1, _ := Mean(d1)
	mean2, _ := Mean(d2)
	var sum float64
	for i := 0; i < d1.Len(); i++ {
		sum += (d1.Get(i) - mean1) * (d2.Get(i) - mean2)
	}
	want := sum / float64(d1.Len()-1)
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("Covariance = %v, want %v", got, want)
	}
}

func TestCovariancePopulation_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
	}{
		{"empty first", Float64Data{}, Float64Data{1, 2}, EmptyInputErr},
		{"empty second", Float64Data{1, 2}, Float64Data{}, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := CovariancePopulation(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestCovariancePopulation_Normal(t *testing.T) {
	d1 := Float64Data{2, 4, 6, 8}
	d2 := Float64Data{1, 3, 5, 7}
	got, err := CovariancePopulation(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	mean1, _ := Mean(d1)
	mean2, _ := Mean(d2)
	var sum float64
	for i := 0; i < d1.Len(); i++ {
		sum += (d1.Get(i) - mean1) * (d2.Get(i) - mean2)
	}
	want := sum / float64(d1.Len())
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("CovariancePopulation = %v, want %v", got, want)
	}
}

func TestVariance_Errors(t *testing.T) {
	empty := Float64Data{}
	if _, err := PopulationVariance(empty); !errors.Is(err, EmptyInputErr) {
		t.Fatalf("PopulationVariance empty: expected %v, got %v", EmptyInputErr, err)
	}
	if _, err := SampleVariance(empty); !errors.Is(err, EmptyInputErr) {
		t.Fatalf("SampleVariance empty: expected %v, got %v", EmptyInputErr, err)
	}
}

func TestVariance_Values(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	pop, err := PopulationVariance(data)
	if err != nil {
		t.Fatalf("PopulationVariance error: %v", err)
	}
	samp, err := SampleVariance(data)
	if err != nil {
		t.Fatalf("SampleVariance error: %v", err)
	}
	mean, _ := Mean(data)
	var sumSq float64
	for _, v := range data {
		diff := v - mean
		sumSq += diff * diff
	}
	wantPop := sumSq / float64(len(data))
	wantSamp := sumSq / float64(len(data)-1)
	if math.Abs(pop-wantPop) > 1e-9 {
		t.Fatalf("PopulationVariance = %v, want %v", pop, wantPop)
	}
	if math.Abs(samp-wantSamp) > 1e-9 {
		t.Fatalf("SampleVariance = %v, want %v", samp, wantSamp)
	}
}
