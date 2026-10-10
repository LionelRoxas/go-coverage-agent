package stats

import (
	"errors"
	"math"
	"testing"
)

type rmsTestCase struct {
	name    string
	input   []float64
	want    float64
	wantErr error
}

func TestRMS(t *testing.T) {
	cases := []rmsTestCase{{
		name:    "empty",
		input:   []float64{},
		want:    math.NaN(),
		wantErr: ErrEmptyInput,
	}, {
		name:    "single",
		input:   []float64{3},
		want:    3,
		wantErr: nil,
	}, {
		name:    "multiple",
		input:   []float64{1, 2, 3, 4},
		want:    math.Sqrt((1*1 + 2*2 + 3*3 + 4*4) / 4.0),
		wantErr: nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := RMS(Float64Data(tc.input))
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result for error case, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
			} else if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("RMS = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestFloat64Data_RMS(t *testing.T) {
	cases := []rmsTestCase{{
		name:    "empty",
		input:   []float64{},
		want:    math.NaN(),
		wantErr: ErrEmptyInput,
	}, {
		name:    "two",
		input:   []float64{-2, 2},
		want:    2,
		wantErr: nil,
	}}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			data := Float64Data(tc.input)
			got, err := data.RMS()
			if tc.wantErr != nil {
				if !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result for error case, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.Abs(got-tc.want) > 1e-9 {
				t.Fatalf("RMS = %v, want %v", got, tc.want)
			}
		})
	}
}
