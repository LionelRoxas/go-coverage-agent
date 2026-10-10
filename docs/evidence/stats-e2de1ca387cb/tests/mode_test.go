package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestMode_Coverage(t *testing.T) {
	cases := []struct {
		name    string
		input   Float64Data
		want    []float64
		wantErr error
	}{
		{name: "single element", input: Float64Data{42}, want: []float64{42}, wantErr: nil},
		{name: "empty input", input: Float64Data{}, want: nil, wantErr: EmptyInputErr},
		{name: "all distinct", input: Float64Data{1, 2, 3}, want: []float64{}, wantErr: nil},
		{name: "multiple modes all values", input: Float64Data{1, 1, 2, 2}, want: []float64{}, wantErr: nil},
		{name: "unique mode", input: Float64Data{1, 2, 2, 3}, want: []float64{2}, wantErr: nil},
		{name: "multiple modes partial", input: Float64Data{1, 1, 2, 3, 3}, want: []float64{1, 3}, wantErr: nil},
		{name: "all same values", input: Float64Data{5, 5, 5}, want: []float64{5}, wantErr: nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Mode(tc.input)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if !reflect.DeepEqual(got, tc.want) {
				t.Fatalf("expected %v, got %v", tc.want, got)
			}
		})
	}
}
