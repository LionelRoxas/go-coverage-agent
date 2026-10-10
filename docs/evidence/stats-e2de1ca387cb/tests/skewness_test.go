package stats

import (
	"errors"
	"math"
	"testing"
)

func TestPopulationSkewness_EdgeCases(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr error
	}{
		{"empty", Float64Data{}, math.NaN(), ErrEmptyInput},
		{"single", Float64Data{42}, math.NaN(), ErrEmptyInput},
		{"all_equal", Float64Data{5, 5, 5, 5}, math.NaN(), ErrZero},
		{"symmetric", Float64Data{-1, 0, 1}, 0.0, nil},
		{"general", Float64Data{1, 2, 3, 4, 6}, 0.0, nil}, // expected computed below
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := PopulationSkewness(tc.data)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			// For the "general" case compute expected using the same formula
			if tc.name == "general" {
				// manual computation of population skewness
				n := float64(len(tc.data))
				var sum, sumSq, sumCu float64
				for _, v := range tc.data {
					sum += v
				}
				mean := sum / n
				for _, v := range tc.data {
					d := v - mean
					sumSq += d * d
					sumCu += d * d * d
				}
				variance := sumSq / n
				stdDevCubed := math.Pow(variance, 1.5)
				tc.want = (sumCu / n) / stdDevCubed
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestSampleSkewness_EdgeCases(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		want    float64
		wantErr error
	}{
		{"too_few", Float64Data{1, 2}, math.NaN(), ErrEmptyInput},
		{"all_equal", Float64Data{3, 3, 3}, math.NaN(), ErrZero},
		{"symmetric", Float64Data{-2, 0, 2}, 0.0, nil},
		{"general", Float64Data{1, 2, 3, 4, 6}, 0.0, nil}, // expected computed below
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := SampleSkewness(tc.data)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.name == "general" {
				// compute population skewness first
				pop, _ := PopulationSkewness(tc.data)
				n := float64(len(tc.data))
				expected := pop * math.Sqrt(n*(n-1)) / (n - 2)
				tc.want = expected
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("got %v, want %v", got, tc.want)
			}
		})
	}
}

func TestSkewness_Forwards(t *testing.T) {
	data := Float64Data{-1, 0, 1}
	want, err1 := PopulationSkewness(data)
	if err1 != nil {
		t.Fatalf("PopulationSkewness unexpected error: %v", err1)
	}
	got, err2 := Skewness(data)
	if err2 != nil {
		t.Fatalf("Skewness unexpected error: %v", err2)
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("Skewness forward mismatch: got %v, want %v", got, want)
	}
}
