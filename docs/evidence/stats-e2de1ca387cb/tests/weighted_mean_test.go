package stats

import (
	"errors"
	"math"
	"testing"
)

func TestWeightedMean_ErrorsAndNormal(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		weights Float64Data
		want    float64
		wantErr error
	}{
		{"EmptyData", Float64Data{}, Float64Data{1}, math.NaN(), ErrEmptyInput},
		{"SizeMismatch", Float64Data{1, 2}, Float64Data{1}, math.NaN(), ErrSize},
		{"NegativeWeight", Float64Data{1, 2}, Float64Data{1, -1}, math.NaN(), ErrNegative},
		{"ZeroTotalWeight", Float64Data{1, 2}, Float64Data{0, 0}, math.NaN(), ErrZero},
		{"UniformWeights", Float64Data{1, 2, 3}, Float64Data{1, 1, 1}, 2.0, nil},
		{"MixedWeights", Float64Data{1, 2}, Float64Data{0, 2}, 2.0, nil},
	}
	for _, tc := range cases {
		tc := tc // capture range variable
		t.Run(tc.name, func(t *testing.T) {
			got, err := WeightedMean(tc.data, tc.weights)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if math.IsNaN(tc.want) {
					if !math.IsNaN(got) {
						t.Fatalf("expected NaN, got %v", got)
					}
				} else {
					if math.Abs(got-tc.want) > 1e-9 {
						t.Fatalf("expected %v, got %v", tc.want, got)
					}
				}
			}
		})
	}
}

func TestFloat64Data_WeightedMean_Wrapper(t *testing.T) {
	data := Float64Data{10, 20}
	weights := Float64Data{1, 3}
	want := float64(10*1+20*3) / float64(1+3) // 17.5
	got, err := data.WeightedMean(weights)
	if err != nil {
		t.Fatalf("unexpected error %v", err)
	}
	if math.Abs(got-want) > 1e-9 {
		t.Fatalf("expected %v, got %v", want, got)
	}
}
