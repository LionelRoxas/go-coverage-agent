package stats

import (
	"errors"
	"testing"
)

func modeSlicesEqual(a, b []float64) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func TestMode_EdgeCases(t *testing.T) {
	cases := []struct {
		name      string
		input     []float64
		want      []float64
		wantErr   error
		wantEmpty bool
	}{
		{name: "EmptyInput", input: []float64{}, wantErr: EmptyInputErr, wantEmpty: true},
		{name: "SingleElement", input: []float64{5.5}, want: []float64{5.5}},
		{name: "SimpleMode", input: []float64{1, 2, 2, 3}, want: []float64{2}},
		{name: "MultipleModes", input: []float64{1, 1, 2, 2, 3}, want: []float64{1, 2}},
		{name: "FinalRunGreater", input: []float64{1, 2, 2, 2}, want: []float64{2}},
		{name: "DistinctValues", input: []float64{1, 2, 3, 4}, wantEmpty: true},
		{name: "AllModesCoverAll", input: []float64{1, 1, 2, 2}, wantEmpty: true},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Mode(Float64Data(tc.input))
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if len(got) != 0 {
					t.Fatalf("expected empty result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if tc.wantEmpty {
				if len(got) != 0 {
					t.Fatalf("expected empty slice, got %v", got)
				}
				return
			}
			if !modeSlicesEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
