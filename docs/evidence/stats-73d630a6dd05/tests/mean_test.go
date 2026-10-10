package stats

import (
	"errors"
	"math"
	"testing"
)

func meanApproxEqual(got, want float64) bool {
	const eps = 1e-9
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= eps
}

func TestGeometricMean(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    float64
		wantErr error
	}{
		{name: "empty input", input: Float64Data{}, want: math.NaN(), wantErr: EmptyInputErr},
		{name: "negative value", input: Float64Data{-2, 3}, want: math.NaN(), wantErr: NegativeErr},
		{name: "zero value", input: Float64Data{0, 5}, want: math.NaN(), wantErr: ZeroErr},
		{name: "positive values", input: Float64Data{2, 8, 4}, want: math.Exp((math.Log(2) + math.Log(8) + math.Log(4)) / 3), wantErr: nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := GeometricMean(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr != nil {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if !meanApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}

type meanCase struct {
	name    string
	input   Float64Data
	want    float64
	wantErr error
}

var meanCases = []meanCase{
	{
		name:    "empty input",
		input:   Float64Data{},
		want:    math.NaN(),
		wantErr: EmptyInputErr,
	},
	{
		name:    "negative value",
		input:   Float64Data{-1, 2, 3},
		want:    math.NaN(),
		wantErr: NegativeErr,
	},
	{
		name:    "zero value",
		input:   Float64Data{0, 1, 2},
		want:    math.NaN(),
		wantErr: ZeroErr,
	},
	{
		name:    "normal case",
		input:   Float64Data{1, 2, 4},
		want:    3.0 / (1 + 0.5 + 0.25),
		wantErr: nil,
	},
}

func TestHarmonicMean(t *testing.T) {
	for _, tc := range meanCases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := HarmonicMean(tc.input)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !meanApproxEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
