package stats

import (
	"errors"
	"math"
	"testing"
)

func deviationFloatEqual(got, want float64) bool {
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= 1e-9
}

func TestMedianAbsoluteDeviationPopulation(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{
			name:    "EmptyInput",
			input:   Float64Data{},
			want:    math.NaN(),
			wantErr: EmptyInputErr,
		},
		{
			name:    "OddLength",
			input:   Float64Data{1, 2, 3, 4, 5},
			want:    1.0,
			wantErr: nil,
		},
		{
			name:    "EvenLength",
			input:   Float64Data{1, 2, 3, 4},
			want:    1.0,
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := MedianAbsoluteDeviationPopulation(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !deviationFloatEqual(got, tc.want) {
					t.Errorf("MAD = %v, want %v", got, tc.want)
				}
			} else {
				if !math.IsNaN(got) {
					t.Errorf("expected NaN result on error, got %v", got)
				}
			}
		})
	}
}

func TestMedianAbsoluteDeviation(t *testing.T) {
	input := Float64Data{10, 20, 30, 40, 50}
	want := 10.0 // median is 30, deviations are 20,10,0,10,20 => median 10
	got, err := MedianAbsoluteDeviation(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !deviationFloatEqual(got, want) {
		t.Errorf("MedianAbsoluteDeviation = %v, want %v", got, want)
	}
}

func TestStandardDeviationSample(t *testing.T) {
	// Empty input case
	empty := Float64Data{}
	got, err := StandardDeviationSample(empty)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
	if !math.IsNaN(got) {
		t.Errorf("expected NaN result for empty input, got %v", got)
	}

	// Non‑empty case (basic sanity check)
	data := Float64Data{2, 4, 4, 4, 5, 5, 7, 9}
	// Expected sample standard deviation ≈ sqrt(32/7)
	expected := math.Sqrt(32.0 / 7.0)
	got, err = StandardDeviationSample(data)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !deviationFloatEqual(got, expected) {
		t.Errorf("StandardDeviationSample = %v, want %v", got, expected)
	}
}
